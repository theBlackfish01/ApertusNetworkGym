// Words an operator reads: scopes, routes, the stream's kinds of instruction, verdicts.

import type { AuditRow, Policy } from "./types";

export const KIND: Record<string, string> = {
  supported: "in the language",
  new: "a type never shown",
  partial: "carried in part",
  not_instruction: "no routing instruction",
  faulty: "a place outside the network",
  typed: "typed by you",
  none: "",
};

export const LANGUAGE: Record<string, string> = { en: "English", de: "German", fr: "French", it: "Italian" };

export function scopeText(scope: string | null | undefined): string {
  if (!scope || scope === "any") return "all requests";
  const [kind, value] = scope.split(":");
  if (kind === "rate") return `${value}G requests`;
  if (kind === "from") return `requests from ${value}`;
  if (kind === "to") return `requests to ${value}`;
  return scope;
}

export function routeText(route: string[] | null | undefined): string {
  return route && route.length ? route.join(" → ") : "rejected";
}

export function holds(policy: Policy, now: number): string {
  if (policy.until === null || policy.expires === null) return "until withdrawn";
  return `${Math.max(0, policy.expires - now).toFixed(1)} h left`;
}

export function remaining(policy: Policy, now: number): number | null {
  if (policy.until === null || policy.expires === null) return null;
  return Math.max(0, Math.min(1, (policy.expires - now) / policy.until));
}

export function pct(part: number, whole: number, digits = 1): string {
  return whole ? `${((100 * part) / whole).toFixed(digits)}%` : "–";
}

export type Verdict = { tone: "ok" | "no" | "na"; text: string; title: string };

/** The badge of a decision: what it was judged against, and whether it held. */
export function verdict(row: Pick<AuditRow, "respects" | "judged">): Verdict {
  const judged = row.judged ?? "";
  const short = judged === "the instruction and the policies together"
    ? "instruction and policies"
    : judged.replace(/^the /, "").replace(", policies aside", "");
  if (row.respects === true) return { tone: "ok", text: `respects ${short}`, title: `judged against ${judged}` };
  if (row.respects === false) return { tone: "no", text: `breaks ${short}`, title: `judged against ${judged}` };
  return { tone: "na", text: "nothing to respect", title: "no instruction and no policy covered this request" };
}

/** "The policy line" of the format, as a readable list of its non-default fields. */
export function lineFields(line: string): [string, string][] {
  return line
    .split(";")
    .map((part) => part.trim().split("="))
    .filter((kv): kv is [string, string] => kv.length === 2 && !["none", "any", "open"].includes(kv[1]))
    .map(([k, v]) => [k, v]);
}

/** The fields where the line applied and the recorded meaning differ: [field, applied, meant]. */
export function lineDiff(applied: string, meant: string): [string, string, string][] {
  const parse = (line: string) =>
    new Map(line.split(";").map((part) => part.trim().split("=")).filter((kv) => kv.length === 2).map(([k, v]) => [k, v] as [string, string]));
  const a = parse(applied), m = parse(meant);
  return [...new Set([...a.keys(), ...m.keys()])].filter((k) => a.get(k) !== m.get(k)).map((k) => [k, a.get(k) ?? "–", m.get(k) ?? "–"]);
}
