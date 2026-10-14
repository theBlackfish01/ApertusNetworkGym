// What src/console.py sends: /api/state, /api/request, /api/race and the read endpoints.

export interface SpecJSON {
  status: string;
  avoid: [string, string][];
  prefer: string[];
  nodes?: string[];
  via?: string[];
  max_hops?: number;
  max_km?: number;
  path?: number;
  rest?: boolean;
  scope?: string;
  until?: number;
}

export interface NodeRow { name: string; lon: number; lat: number }
export interface LinkRow { a: string; b: string; km?: number; used: number }

export interface Policy {
  id: number;
  text: string;
  scope: string;
  until: number | null;
  created: number;
  expires: number | null;
  ended: number | null;
  active: boolean;
  asked: boolean;
  in_scope: number;
  changed: number;
  rejected: number;
  violations: number;
  line: string;
  readback: string;
  spec: SpecJSON;
}

export interface Reading {
  reader: string;
  line: string;
  spec: SpecJSON;
  readback: string;
  status: string;
  applies: boolean;
  tapi: unknown;
  seconds: number;
  decision: { route: string[] | null; reject: boolean; to_decider: boolean };
}

export interface Question {
  id: number;
  text: string;
  why: string;
  readings: Reading[];
  truth: string | null;
  request: { n: number; source: string; destination: string; bit_rate: number };
}

export interface FeedEvent {
  n: number;
  hour: number;
  request: number;
  kind: string;
  level: "operator" | "inspect";
  title: string;
  detail: string | null;
  data: Record<string, any> | null;
}

export interface AuditRow {
  n: number;
  hour: number;
  source: string;
  destination: string;
  bit_rate: number;
  instruction: string;
  kind: string;
  line: string;
  policies: number[];
  effective: string;
  who: string;
  asked: boolean;
  answer: string;
  path: number | null;
  slot: number | null;
  route: string[] | null;
  blocked: boolean;
  invalid: boolean;
  respects: boolean | null;
  judged: string | null;
  respects_policies: boolean | null;
  broken: number[];
  truth: string | null;
  meant: string | null;
  tapi: unknown;
}

export interface Stats {
  served: number;
  processed: number;
  blocking: number;
  rejected: number;
  violations: number;
  policy_violations: number;
  questions: number;
  decider: number;
  guarded: number;
  flagged: number;
  unread: number;
  policies_active: number;
  load: number;
  seed: number;
}

export interface State {
  topology: string;
  now: number;
  mode: { live: boolean; hybrid: string; reader: string; decider: string; base_url: string };
  settings: { arrivals: boolean; mix: boolean; auto_answer: boolean };
  nodes: NodeRow[];
  links: LinkRow[];
  policies: Policy[];
  in_force: { line: string; spec: SpecJSON; count: number; covering: number[] };
  pending: {
    n: number;
    source: string;
    destination: string;
    bit_rate: number;
    paths: string[][];
    instruction: { text: string; kind: string; lang: string; typed: boolean };
  };
  question: Question | null;
  last_route: string[] | null;
  stats: Stats;
  feed: FeedEvent[];
  audit: AuditRow[];
  series: { violation: string; rejected: string; asked: string; decider: string; guard: string };
  race_default: { load: number; seed: number };
}

export interface CandidatePath {
  index: number;
  nodes: string[];
  hops: number;
  km: number;
  free_slots: number;
  modulation: string | null;
  slots_needed: number | null;
  first_slot: number | null;
  blocks: [number, number][];
  feasible: boolean;
  excluded: string[];
}

export interface Inspect {
  paths: CandidatePath[];
  steps: { by: string; from: number[]; kept: number[] }[];
  tie_break: string;
  admissible: number[];
  chosen: number | null;
  slot: number | null;
  engine: number | null;
}

export interface Strip { a: string; b: string; occupied: string; block: [number, number] }

export interface RequestDetail {
  ok?: boolean;
  error?: string;
  decided?: boolean;
  pruned?: boolean; // a decided request older than the last 2,000: no candidates, no spectrum
  row: Partial<AuditRow> & { n: number; source: string; destination: string; bit_rate: number; inspect?: Inspect;
                             spectrum?: Strip[]; used?: number[]; effective: string };
}

export interface LaneOutcome { route: string[] | null; rejected: boolean; violation: boolean; invalid: boolean; who: string }

export interface RaceLane {
  key: string;
  label: string;
  what: string;
  stored: string;
  served: number;
  violations: number;
  rejected: number;
  classes: Record<string, { n: number; violations: number }>;
  series: number[];
  last: LaneOutcome | null;
  links: LinkRow[];
  stored_violations: number | null;
  same_as_stored: boolean | null;
}

export interface RaceRequest {
  n: number;
  source: string;
  destination: string;
  bit_rate: number;
  text: string;
  class: string;
  kind: string;
  lanes: Record<string, LaneOutcome>;
}

export interface RaceState {
  status: "off" | "preparing" | "ready" | "error";
  progress?: number;
  error?: string | null;
  load?: number;
  seed?: number;
  window?: number;
  every?: number;
  lanes?: RaceLane[];
  requests?: number;
  last?: RaceRequest | null;
  recent?: RaceRequest[];
  done?: number;
}

export interface PolicyRead {
  error?: string;
  text: string;
  line: string;
  status: string;
  applies: boolean;
  readback: string;
  scope: string;
  until: number | null;
  tapi: unknown;
  conflicts: { kind: string; why: string; with: number | null; with_text?: string }[];
  seconds: number;
  preview: null | { horizon: number; covers: number; without: { blocked: number }; with: { blocked: number; changed: number } };
}

export interface InstructionRead {
  error?: string;
  ok?: boolean;
  text: string;
  readings: Reading[];
  differ?: boolean;
  decide_differently?: boolean;
  request?: State["pending"];
}

export interface Recorded {
  instructions: { text: string; set: string; lang: string; kind: string }[];
  policies: { text: string; set: string; lang: string; kind: string }[];
}
