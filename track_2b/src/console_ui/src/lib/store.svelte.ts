// The page's state and every action it can take, in one place (Svelte 5 runes).

import { get, message, post } from "./api";
import type { Filter } from "./feed";
import type { AuditRow, InstructionRead, PolicyRead, RaceState, Recorded, RequestDetail, State } from "./types";

export type Mode = "operate" | "race";
export type Tab = "audit" | "report" | "timeline" | "metrics" | null;
type Sheet =
  | { kind: "policy"; read: PolicyRead }
  | { kind: "instruction"; read: InstructionRead }
  | { kind: "settled"; line: string }
  | null;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

class ConsoleStore {
  state = $state<State | null>(null);
  recorded = $state<Recorded>({ instructions: [], policies: [] });
  error = $state("");
  connected = $state(false);

  // what the operator looks at
  mode = $state<Mode>("operate");
  detail = $state(false); // the model's lines in the feed and the rail
  filter = $state<Filter>("all");
  tab = $state<Tab>(null);
  hover = $state<number | null>(null); // a policy lit up on the map
  pin = $state<number | null>(null); // a request whose route (and network) the map shows
  pinDetail = $state<RequestDetail["row"] | null>(null);
  inspect = $state<number | null>(null); // the request open in the inspector
  animate = $state(false); // the last update decided a request: draw its route as it is set up

  // the stream
  playing = $state(false);
  pace = $state(500); // ms per request
  private run = 0; // the play loop that may go on: a pause and a quick resume start a new one, and the old one stops
  private raceRun = 0;
  private pinAsk = 0; // the latest "show on the map", so that an older answer cannot land after it

  // the command line
  cmdMode = $state<"policy" | "instruction">("policy");
  sheet = $state<Sheet>(null);
  reading = $state(false);

  // the race
  race = $state<RaceState>({ status: "off" });
  racePlaying = $state(false);
  raceSpeed = $state(2); // requests per tick

  // overlays
  paletteOpen = $state(false);
  tourOpen = $state(false);

  auditByN = $derived(new Map<number, AuditRow>((this.state?.audit ?? []).map((row) => [row.n, row])));
  lastDecision = $derived(this.state?.audit.length ? this.state.audit[this.state.audit.length - 1] : null);

  // ---- the stream ------------------------------------------------------------------------------
  async boot(): Promise<void> {
    for (;;) {
      try {
        await this.refresh();
        this.recorded = await get<Recorded>("/api/recorded");
        this.connected = true;
        void this.raceRefresh();
        return;
      } catch {
        this.connected = false;
        await sleep(2000); // the server may still be building its simulator
      }
    }
  }

  async refresh(): Promise<void> {
    this.state = await get<State>("/api/state");
    this.animate = false;
  }

  async step(count: number): Promise<boolean> {
    try {
      const r = await post<{ rows: AuditRow[]; state: State; error?: string }>("/api/step", { count });
      if (r.error) {
        this.error = r.error;
        this.pause();
        return false;
      }
      this.state = r.state;
      this.animate = r.rows.length > 0;
      this.error = ""; // a pinned request stays on the map until the operator returns to live
      return r.rows.length > 0;
    } catch (error) {
      this.error = message(error);
      this.pause();
      return false;
    }
  }

  async play(): Promise<void> {
    if (this.playing) return;
    this.playing = true;
    const run = ++this.run;
    while (this.playing && run === this.run) {
      if (!this.state || this.state.question) break;
      const started = performance.now();
      const moved = await this.step(this.pace <= 50 ? 5 : 1);
      if (!moved || run !== this.run) break;
      await sleep(Math.max(0, this.pace - (performance.now() - started)));
    }
    if (run === this.run) this.playing = false;
  }

  pause(): void {
    this.playing = false;
    this.run++;
  }

  toggle(): void {
    if (this.playing) this.pause();
    else void this.play();
  }

  async settings(changes: Partial<State["settings"]>): Promise<void> {
    const current = this.state?.settings ?? { arrivals: true, mix: true, auto_answer: false };
    await post("/api/settings", { ...current, ...changes });
    await this.refresh();
  }

  async withdraw(id: number): Promise<void> {
    if (this.hover === id) this.hover = null;
    await post("/api/policy/withdraw", { id });
    await this.refresh();
  }

  async answer(id: number, choice: 1 | 2 | "own", line = ""): Promise<void> {
    const r = await post<{ error?: string }>("/api/answer", { id, choice, line });
    this.error = r.error ?? ""; // an answer that settles the question clears an earlier failure
    await this.refresh();
  }

  // ---- what the map shows --------------------------------------------------------------------
  async pinRequest(n: number): Promise<void> {
    this.setMode("operate");
    if (this.pin === n) {
      this.unpin();
      return;
    }
    const ask = ++this.pinAsk;
    try {
      const detail = await get<RequestDetail>(`/api/request?n=${n}`);
      if (ask !== this.pinAsk || detail.error || !detail.decided) return;
      this.pin = n;
      this.pinDetail = detail.row;
    } catch (error) {
      if (ask === this.pinAsk) this.error = message(error);
    }
  }

  unpin(): void {
    this.pinAsk++;
    this.pin = null;
    this.pinDetail = null;
  }

  /** Operate or race: the view left behind stops, since its transport is hidden. */
  setMode(mode: Mode): void {
    if (mode === this.mode) return;
    if (mode === "race") this.pause();
    else this.racePause();
    this.mode = mode;
  }

  openInspector(n: number): void {
    this.setMode("operate");
    this.inspect = n;
  }

  // ---- the command line ----------------------------------------------------------------------
  async read(text: string): Promise<void> {
    text = text.trim();
    this.error = "";
    this.sheet = null;
    if (!text) return;
    this.reading = true;
    try {
      if (this.cmdMode === "policy") {
        const r = await post<PolicyRead>("/api/policy/read", { text });
        if (r.error) this.error = r.error;
        else this.sheet = { kind: "policy", read: r };
      } else {
        const r = await post<InstructionRead>("/api/instruction", { text });
        if (r.error) this.error = r.error;
        else if (r.readings.length) this.sheet = { kind: "instruction", read: r };
        await this.refresh();
      }
    } catch (error) {
      this.error = message(error);
    } finally {
      this.reading = false;
    }
  }

  async addPolicy(line?: string): Promise<boolean> {
    if (this.sheet?.kind !== "policy") return false;
    const read = this.sheet.read;
    const r = await post<{ error?: string }>("/api/policy/add", { text: read.text, line: line ?? read.line });
    if (r.error) {
      this.error = r.error;
      return false;
    }
    this.sheet = null;
    await this.refresh();
    return true;
  }

  async confirmInstruction(line: string): Promise<void> {
    if (this.sheet?.kind !== "instruction") return;
    const r = await post<{ error?: string; line: string }>("/api/instruction/confirm", { text: this.sheet.read.text, line });
    if (r.error) {
      this.error = r.error;
      return;
    }
    this.sheet = { kind: "settled", line: r.line };
    await this.refresh();
  }

  async clearInstruction(): Promise<void> {
    this.sheet = null;
    this.error = "";
    if (this.cmdMode === "instruction") {
      await post("/api/instruction", { text: "" });
      await this.refresh();
    }
  }

  // ---- the race ------------------------------------------------------------------------------
  async raceRefresh(): Promise<void> {
    this.race = await get<RaceState>("/api/race");
    while (this.race.status === "preparing") {
      await sleep(700);
      this.race = await get<RaceState>("/api/race");
    }
  }

  async raceStart(load: number, seed: number): Promise<void> {
    this.racePause();
    this.race = { ...this.race, status: "preparing", progress: 0 }; // the button is disabled at once, not when the server answers
    const r = await post<RaceState & { error?: string }>("/api/race/start", { load, seed });
    if (r.error && r.status === undefined) {
      this.error = r.error;
      return;
    }
    this.race = r;
    await this.raceRefresh();
  }

  async raceStep(count: number): Promise<number> {
    try {
      const r = await post<RaceState & { error?: string }>("/api/race/step", { count });
      if (r.error && r.status === undefined) {
        this.error = r.error;
        return 0;
      }
      this.race = r;
      return r.done ?? 0;
    } catch (error) {
      this.error = message(error);
      return 0;
    }
  }

  async racePlay(): Promise<void> {
    if (this.racePlaying || this.race.status !== "ready") return;
    this.racePlaying = true;
    const run = ++this.raceRun;
    while (this.racePlaying && run === this.raceRun) {
      const started = performance.now();
      const done = await this.raceStep(this.raceSpeed);
      if (!done || run !== this.raceRun) break;
      await sleep(Math.max(0, 140 - (performance.now() - started)));
    }
    if (run === this.raceRun) this.racePlaying = false;
  }

  racePause(): void {
    this.racePlaying = false;
    this.raceRun++;
  }
}

export const app = new ConsoleStore();
