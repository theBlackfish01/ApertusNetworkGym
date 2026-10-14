<script lang="ts">
  // A guided tour: it drives the stream to the moments worth seeing (a policy arriving, a question, the
  // decider, an inspection, the race) and points at each one. About two minutes; it can serve as the
  // demo video's script.
  import { onDestroy, onMount } from "svelte";
  import { app } from "../lib/store.svelte";

  type Step = { target: string; title: string; text: string; run?: () => Promise<string | void> };

  // Closing the tour stops it driving the stream: every loop and every step after an await checks this.
  let alive = true;
  async function stepUntil(done: () => boolean, max: number): Promise<boolean> {
    for (let i = 0; i < max && alive && !done(); i++) {
      if (app.state?.question) return done();
      if (!(await app.step(1))) break;
    }
    return done();
  }
  // an event of this kind newer than the step's start (an older one still in the feed does not count)
  let since = 0;
  const has = (kind: string) => () => (app.state?.feed ?? []).some((e) => e.kind === kind && e.n > since);

  const STEPS: Step[] = [
    { target: "header", title: "What runs here",
      text: "The whole system on a simulated European optical network (28 cities, 41 links), under the evaluation's load. Apertus 8B reads what an operator types; a rule engine decides every lightpath request. The pill says whether the models answer live or from stored answers.",
      run: async () => {
        app.setMode("operate");
        app.inspect = null;
        if (app.state && (!app.state.settings.arrivals || !app.state.settings.mix || app.state.settings.auto_answer)) {
          await app.settings({ arrivals: true, mix: true, auto_answer: false });
        }
      } },
    { target: "feed", title: "A standing policy arrives",
      text: "Policies arrive in English, German, French and Italian. The reader turns each into one line of the policy language, with a scope and a lifetime, and reads it back; the card says whether that matches what was meant.",
      run: async () => ((await stepUntil(() => (app.state?.feed ?? []).some((e) => e.kind === "policy_added"), 40)) ? undefined : "No policy arrived yet; it will appear in the feed later.") },
    { target: "map", title: "The network",
      text: "Red is what the policies in force avoid, green what they require; the route just set up is cyan, the next request's end points amber. Hover a policy in the right rail to light up exactly what it touches; scroll to zoom, drag to pan.",
      run: async () => {
        const first = app.state?.policies.find((p) => p.active);
        if (first) app.hover = first.id;
      } },
    { target: "feed", title: "Requests and their verdicts",
      text: "Each request card shows the instruction that came with it, what the two readers made of it, who decided, the route, and the verdict: whether the decision respects what was meant.",
      run: async () => {
        app.hover = null;
        await app.step(3);
      } },
    { target: "question", title: "A question, only when it matters",
      text: "When the two readers disagree in a way that would route this request differently, the stream pauses and you choose; each reading shows what it would do. Pick one now, or press Next and the tour answers with the recorded meaning.",
      run: async () => ((await stepUntil(() => !!app.state?.question, 120)) ? undefined : "No disagreement came up in this stretch of the stream.") },
    { target: "feed", title: "Outside the language: the decider",
      text: "An instruction the policy language cannot express goes to the decider, which reads it together with the request; a guard replaces its route if it breaks the part of the line that was read. Its verdict is often red: that is the paper's weak point, measured.",
      run: async () => {
        const q = app.state?.question;
        if (q) {
          const right = q.readings.findIndex((r) => r.line === q.truth);
          await app.answer(q.id, right === 1 ? 2 : 1);
        }
        if (!alive) return;
        since = app.state?.feed.at(-1)?.n ?? 0;
        const found = await stepUntil(has("decider"), 120);
        return found ? undefined : "No instruction outside the language came up yet.";
      } },
    { target: "inspector", title: "Why this route",
      text: "The inspector opens any request: the five candidate paths, the constraint that dropped each one, how the rest were ranked, who decided, and the spectrum the lightpath took on every link.",
      run: async () => {
        if (app.lastDecision) app.openInspector(app.lastDecision.n);
        await new Promise((r) => setTimeout(r, 400));
      } },
    { target: "timeline", title: "The stream so far",
      text: "Every decided request is on the timeline: violations red, questions amber, the guard violet; triangles mark policies coming into force. Click one to see the network as it was when that request was decided.",
      run: async () => {
        app.inspect = null;
      } },
    { target: "race", title: "The race",
      text: "The paper's comparison, live: the evaluation's own stream decided by first fit, the decider alone, the reader with the rule engine, and the hybrid, side by side. Each lane replays the stored answers and is checked against its stored run at the end.",
      run: async () => {
        app.setMode("race");
        if (app.race.status === "off") await app.raceStart(app.state?.race_default.load ?? 390, app.state?.race_default.seed ?? 1);
        if (alive && app.race.status === "ready" && !app.racePlaying) {
          app.raceSpeed = 5;
          void app.racePlay();
        }
      } },
  ];

  let index = $state(0);
  let busy = $state(false);
  let note = $state("");
  let rect = $state<{ x: number; y: number; w: number; h: number } | null>(null);

  function locate() {
    const el = document.querySelector<HTMLElement>(`[data-tour="${STEPS[index].target}"]`);
    if (!el) {
      rect = null;
      return;
    }
    const r = el.getBoundingClientRect();
    rect = { x: r.left, y: r.top, w: r.width, h: r.height };
  }
  let dialog: HTMLDivElement | undefined = $state();
  async function go(i: number) {
    index = i;
    busy = true;
    note = "";
    since = app.state?.feed.at(-1)?.n ?? 0;
    try {
      note = (await STEPS[i].run?.()) ?? "";
    } catch (error) {
      note = String(error);
    }
    if (!alive) return;
    busy = false;
    setTimeout(() => {
      locate();
      dialog?.focus(); // a screen reader reads the step; the keys work at once
    }, 60);
  }
  function close() {
    alive = false;
    app.hover = null;
    app.tourOpen = false;
  }
  onDestroy(() => (alive = false));
  onMount(() => {
    void go(0);
  });
  // the ring around the target, kept inside the viewport so that none of its edges is cut off
  const spot = $derived.by(() => {
    if (!rect) return null;
    const left = Math.max(2, rect.x - 4), top = Math.max(2, rect.y - 4);
    const right = Math.min(window.innerWidth - 2, rect.x + rect.w + 4), bottom = Math.min(window.innerHeight - 2, rect.y + rect.h + 4);
    return { left, top, width: Math.max(0, right - left), height: Math.max(0, bottom - top) };
  });
  const card = $derived.by(() => {
    if (!rect) return { left: 24, top: 80 };
    const width = 380, gap = 14, vw = window.innerWidth, vh = window.innerHeight;
    if (rect.x + rect.w + gap + width < vw) return { left: rect.x + rect.w + gap, top: Math.min(Math.max(12, rect.y), vh - 260) };
    if (rect.x - gap - width > 0) return { left: rect.x - gap - width, top: Math.min(Math.max(12, rect.y), vh - 260) };
    return { left: Math.max(12, Math.min(rect.x, vw - width - 12)), top: Math.min(rect.y + rect.h + gap, vh - 260) };
  });
  function key(event: KeyboardEvent) {
    const el = document.activeElement as HTMLElement | null;
    if (el && (["INPUT", "SELECT", "TEXTAREA"].includes(el.tagName) || el.isContentEditable)) return; // typing, say a line of one's own
    if (event.key === "Escape") close();
    else if (event.key === "ArrowRight" && !busy && index < STEPS.length - 1) void go(index + 1);
    else if (event.key === "ArrowLeft" && !busy && index > 0) void go(index - 1);
    else return;
    event.preventDefault();
  }
</script>

<svelte:window onresize={locate} onkeydown={key} />

{#if spot}
  <div class="spot" style:left="{spot.left}px" style:top="{spot.top}px" style:width="{spot.width}px" style:height="{spot.height}px"></div>
{:else}
  <div class="veil"></div>
{/if}
<div class="card" role="dialog" aria-label="guided tour" tabindex="-1" bind:this={dialog} style:left="{card.left}px" style:top="{card.top}px">
  <div class="count">{index + 1} of {STEPS.length}</div>
  <h3>{STEPS[index].title}</h3>
  <p>{busy ? "Working…" : STEPS[index].text}</p>
  {#if note && !busy}<p class="warn">{note}</p>{/if}
  <div class="row">
    <button class="ghost" onclick={close}>End the tour</button>
    <span class="spacer"></span>
    <button class="ghost" disabled={busy || index === 0} onclick={() => go(index - 1)}>Back</button>
    {#if index < STEPS.length - 1}
      <button class="primary" disabled={busy} onclick={() => go(index + 1)}>Next</button>
    {:else}
      <button class="primary" onclick={close}>Done</button>
    {/if}
  </div>
</div>

<style>
  .spot { position: fixed; z-index: 70; border: 2px solid var(--cyan); border-radius: 10px; box-shadow: 0 0 0 9999px #000a; pointer-events: none;
          transition: left 0.3s, top 0.3s, width 0.3s, height 0.3s; }
  .veil { position: fixed; inset: 0; z-index: 70; background: #000a; pointer-events: none; }
  .card { position: fixed; z-index: 71; width: 380px; padding: 14px 16px; background: var(--panel2); border: 1px solid var(--cyan); border-radius: 12px;
          box-shadow: 0 16px 40px #000c; }
  .card:focus { outline: none; } /* focused for the keys and screen readers; its border already marks it */
  .count { font-size: 11px; color: var(--dim); }
  h3 { margin: 2px 0 6px; font-size: 15px; }
  p { margin: 0 0 8px; line-height: 1.5; }
  .row { display: flex; gap: 6px; align-items: center; }
  .spacer { flex: 1; }
</style>
