<script lang="ts">
  // The open question: both readings, read back, with what each would do to the request.
  import { routeText } from "../lib/format";
  import { app } from "../lib/store.svelte";
  import type { Question } from "../lib/types";

  let { q }: { q: Question } = $props();
  let own = $state("");
  let filled = -1; // the question whose first reading the field was filled with: a refresh of the same one keeps what was typed
  $effect(() => {
    if (q.id === filled) return;
    filled = q.id;
    own = q.readings[0]?.line ?? "";
  });
  function consequence(d: Question["readings"][number]["decision"]): string {
    if (d.to_decider) return "would hand this request to the decider";
    if (d.reject || !d.route) return "would reject this request";
    return `would route it ${routeText(d.route)}`;
  }
</script>

<section class="q" aria-live="polite" data-tour="question">
  <h2 class="warn">You are asked</h2>
  <div class="box">
    <div class="dim small">request #{q.request.n} · {q.request.source} → {q.request.destination}, {q.request.bit_rate}G · {q.why}</div>
    <div class="quote">{q.text}</div>
    {#each q.readings as r, i (r.reader)}
      <div class="reading">
        <div><b>{r.reader}</b> <span class="dim">{r.status}</span></div>
        <div class="rb">{r.readback}</div>
        <div class="dim small">{consequence(r.decision)}</div>
        {#if app.detail}<div class="mono">{r.line}</div>{/if}
        <button class="primary" onclick={() => app.answer(q.id, (i + 1) as 1 | 2)}>Use reading {i + 1}</button>
      </div>
    {/each}
    <details>
      <summary>write the line yourself</summary>
      <div class="row">
        <input type="text" bind:value={own} aria-label="your line" />
        <button onclick={() => app.answer(q.id, "own", own)}>Use my line</button>
      </div>
    </details>
    {#if app.detail && q.truth}<div class="dim small">recorded meaning: <span class="mono">{q.truth}</span></div>{/if}
  </div>
</section>

<style>
  .q { padding: 11px 12px 4px; }
  h2 { margin-bottom: 7px; }
  .box { padding: 10px 12px; border: 1px solid var(--amber); border-radius: 9px; background: #1b1609; box-shadow: 0 0 0 1px #f3b63f22; }
  .small { font-size: 12px; }
  .quote { margin: 6px 0; }
  .reading { padding: 8px 9px; border: 1px solid var(--line2); border-radius: 7px; margin-top: 7px; background: var(--panel2); }
  .reading button { margin-top: 7px; }
  .rb { margin: 2px 0 4px; }
  details { margin-top: 8px; }
  .row { display: flex; gap: 6px; margin-top: 6px; }
  .row input { flex: 1; min-width: 0; }
</style>
