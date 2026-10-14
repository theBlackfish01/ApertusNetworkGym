import { describe, expect, it } from "vitest";
import { buildGroups, filterGroups, policyProblem, requestProblem } from "./feed";
import { holds, lineDiff, lineFields, pct, remaining, routeText, scopeText, verdict } from "./format";
import { linkKey, project, routeLinks } from "./geo";
import type { AuditRow, FeedEvent, Policy } from "./types";

let n = 0;
function ev(kind: string, request: number, extra: Partial<FeedEvent> = {}): FeedEvent {
  n += 1;
  return { n, hour: 7.5, request, kind, level: "operator", title: kind, detail: null, data: null, ...extra };
}

describe("feed groups", () => {
  // the order the server writes them: a policy arrives during request 1, then request 1 is decided
  // (its decision event is logged after the request is counted, so request = 2 and data.n = 1)
  const feed: FeedEvent[] = [
    ev("start", 1),
    ev("policy_in", 1, { detail: "avoid Munich for 5 hours" }),
    ev("policy_read", 1, { data: { right: true, line: "avoid=Munich; scope=any; until=5h" } }),
    ev("policy_added", 1, { title: "policy 1 in force, for 5 h", data: { policy: 1, source: "stream", line: "avoid=Munich; scope=any" } }),
    ev("instruction", 1, { detail: "keep off Zurich-Milan", data: { kind: "supported", lang: "en" } }),
    ev("reading", 1, { title: "readers agree: Avoid the link Zurich-Milan." }),
    ev("decision", 2, { data: { n: 1, respects: true } }),
    ev("conflict", 2, { title: "contradiction with policy 1", data: { policy: 2, with: 1 } }),
    ev("policy_added", 2, { title: "policy 2 in force, until withdrawn", data: { policy: 2, source: "operator" } }),
    ev("instruction", 2, { detail: "fewer than 120 free slots", data: { kind: "new", lang: "en" } }),
    ev("reading", 2, { title: "readers differ" }),
    ev("question", 2, { title: "readers differ: you are asked" }),
    ev("provisional", 2, { level: "inspect", title: "first reading kept" }),
  ];

  it("puts each request's and each policy's events together, newest first", () => {
    const groups = buildGroups(feed, false);
    const kinds = groups.map((g) => `${g.type}:${g.n ?? g.policy ?? ""}`);
    expect(kinds).toEqual(["request:2", "policy:2", "request:1", "policy:1", "note:"]);
    const first = groups.find((g) => g.type === "request" && g.n === 1)!;
    expect(first.events.map((e) => e.kind)).toEqual(["instruction", "reading", "decision"]);
    const typed = groups.find((g) => g.policy === 2)!;
    expect(typed.events.map((e) => e.kind)).toEqual(["conflict", "policy_added"]); // the conflict came before "in force"
  });

  it("hides the internal steps unless the model's lines are shown", () => {
    const quiet = buildGroups(feed, false).find((g) => g.n === 2)!;
    const full = buildGroups(feed, true).find((g) => g.n === 2)!;
    expect(quiet.events.some((e) => e.kind === "provisional")).toBe(false);
    expect(full.events.some((e) => e.kind === "provisional")).toBe(true);
  });

  it("finds the problems", () => {
    const groups = buildGroups(feed, false);
    const audit = new Map<number, AuditRow>([[1, { n: 1, respects: true, respects_policies: null } as AuditRow]]);
    expect(requestProblem(groups.find((g) => g.n === 1)!, audit.get(1))).toBe(false);
    expect(requestProblem(groups.find((g) => g.n === 2)!, undefined)).toBe(true); // a question
    expect(policyProblem(groups.find((g) => g.policy === 2)!)).toBe(true); // a conflict
    expect(filterGroups(groups, "problems", audit).map((g) => g.n ?? g.policy)).toEqual([2, 2]);
    expect(filterGroups(groups, "policies", audit).every((g) => g.type !== "request")).toBe(true);
    expect(filterGroups(groups, "requests", audit).map((g) => g.n)).toEqual([2, 1]);
  });
});

describe("words", () => {
  it("writes scopes, routes and shares", () => {
    expect(scopeText("any")).toBe("all requests");
    expect(scopeText("rate:400")).toBe("400G requests");
    expect(scopeText("to:Lyon")).toBe("requests to Lyon");
    expect(scopeText("from:Paris")).toBe("requests from Paris");
    expect(routeText(["Hamburg", "Berlin"])).toBe("Hamburg → Berlin");
    expect(routeText(null)).toBe("rejected");
    expect(pct(1, 3)).toBe("33.3%");
    expect(pct(1, 0)).toBe("–");
  });

  it("says what a decision was judged against", () => {
    expect(verdict({ respects: true, judged: "the instruction and the policies together" }).text).toBe("respects instruction and policies");
    expect(verdict({ respects: false, judged: "the instruction's own rule, policies aside" })).toMatchObject({ tone: "no", text: "breaks instruction's own rule" });
    expect(verdict({ respects: null, judged: null }).tone).toBe("na");
  });

  it("reads a policy's lifetime and a line's fields", () => {
    const p = { until: 10, expires: 17.5 } as Policy;
    expect(holds(p, 12.5)).toBe("5.0 h left");
    expect(remaining(p, 12.5)).toBeCloseTo(0.5);
    expect(holds({ until: null, expires: null } as Policy, 3)).toBe("until withdrawn");
    expect(lineFields("avoid=Munich; via=none; hops=4; km=any; prefer=km; until=open")).toEqual([["avoid", "Munich"], ["hops", "4"], ["prefer", "km"]]);
  });

  it("names only the fields where the meaning and the line applied differ", () => {
    const applied = "avoid=none; via=none; hops=any; km=1050; path=any; prefer=km; rest=none";
    expect(lineDiff(applied, applied.replace("rest=none", "rest=more"))).toEqual([["rest", "none", "more"]]);
    expect(lineDiff(applied, applied)).toEqual([]);
  });
});

describe("the map", () => {
  it("projects into the frame and keys links without direction", () => {
    const P = project([{ name: "A", lon: 0, lat: 50 }, { name: "B", lon: 10, lat: 40 }], 800, 560, 30);
    for (const p of Object.values(P)) {
      expect(p.x).toBeGreaterThanOrEqual(29.9);
      expect(p.x).toBeLessThanOrEqual(770.1);
      expect(p.y).toBeGreaterThanOrEqual(29.9);
      expect(p.y).toBeLessThanOrEqual(530.1);
    }
    expect(P.A.y).toBeLessThan(P.B.y); // north is up
    expect(linkKey("B", "A")).toBe(linkKey("A", "B"));
    expect([...routeLinks(["A", "B", "C"])]).toEqual(["A|B", "B|C"]);
  });
});
