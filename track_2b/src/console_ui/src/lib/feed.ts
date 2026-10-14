// The feed as cards: one per request, one per policy, and short notes for the rest.
//
// The server's feed is a flat list of events (src/console.py, Console._event). A request's events
// share its number (a decision event carries it in data.n, since it is logged after the request is
// counted). A policy's events come together: it arrives, is read, conflicts are named, it is in
// force; a typed policy has no "arrives" event, and its conflicts come just before "in force".

import type { AuditRow, FeedEvent } from "./types";

export const REQUEST_KINDS = new Set(["instruction", "reading", "provisional", "question", "answer", "decider", "guard", "decision"]);

export interface Group {
  type: "request" | "policy" | "note";
  n?: number; // the request's number
  policy?: number; // the policy's id, once it is in force
  events: FeedEvent[];
  added?: FeedEvent;
  last: number; // the newest event's number, for ordering
}

export function buildGroups(feed: FeedEvent[], detail: boolean): Group[] {
  const groups: Group[] = [];
  const byRequest = new Map<number, Group>();
  let policy: Group | null = null;
  for (const e of feed) {
    if (!detail && e.level !== "operator") continue;
    const kind = e.kind;
    const unreadPolicy = kind === "unread" && policy !== null && policy.added === undefined;
    if (REQUEST_KINDS.has(kind) || (kind === "unread" && !unreadPolicy)) {
      const n = (e.data?.n as number | undefined) ?? e.request;
      let group = byRequest.get(n);
      if (!group) {
        group = { type: "request", n, events: [], last: 0 };
        byRequest.set(n, group);
        groups.push(group);
      }
      group.events.push(e);
      policy = null;
    } else if (kind === "policy_in") {
      policy = { type: "policy", events: [e], last: 0 };
      groups.push(policy);
    } else if (kind === "policy_read" || kind === "not_applied" || unreadPolicy) {
      if (!policy) {
        policy = { type: "policy", events: [], last: 0 };
        groups.push(policy);
      }
      policy.events.push(e);
    } else if (kind === "conflict" || kind === "policy_added") {
      if (!policy || policy.added) {
        policy = { type: "policy", events: [], last: 0 };
        groups.push(policy);
      }
      policy.events.push(e);
      if (kind === "policy_added") {
        policy.added = e;
        policy.policy = e.data?.policy as number | undefined;
      }
    } else {
      groups.push({ type: "note", events: [e], last: 0 });
      policy = null;
    }
  }
  for (const group of groups) group.last = Math.max(...group.events.map((e) => e.n));
  return groups.sort((a, b) => b.last - a.last);
}

export function requestProblem(group: Group, row: AuditRow | undefined): boolean {
  return (
    (row !== undefined && (row.respects === false || row.respects_policies === false)) ||
    group.events.some((e) => e.kind === "question" || e.kind === "guard" || e.kind === "unread")
  );
}

export function policyProblem(group: Group): boolean {
  return group.events.some(
    (e) => e.kind === "conflict" || e.kind === "not_applied" || e.kind === "unread" || (e.kind === "policy_read" && e.data?.right === false),
  );
}

export type Filter = "all" | "requests" | "policies" | "problems";

export function filterGroups(groups: Group[], filter: Filter, audit: Map<number, AuditRow>): Group[] {
  return groups.filter((group) => {
    if (filter === "requests") return group.type === "request";
    if (filter === "policies") return group.type === "policy" || (group.type === "note" && group.events[0].kind.startsWith("policy"));
    if (filter === "problems") {
      if (group.type === "request") return requestProblem(group, audit.get(group.n!));
      return group.type === "policy" && policyProblem(group);
    }
    return true;
  });
}
