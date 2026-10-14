<script lang="ts">
  // One request: its instruction, what the readers made of it, a question, the decider or the guard,
  // the route, and the verdict. Click shows the request on the map; "inspect" opens the candidates.
  import type { Group } from "../lib/feed";
  import { requestProblem } from "../lib/feed";
  import { KIND, routeText, verdict } from "../lib/format";
  import { app } from "../lib/store.svelte";

  let { group }: { group: Group } = $props();
  const row = $derived(app.auditByN.get(group.n!));
  const ins = $derived(group.events.find((e) => e.kind === "instruction"));
  const decided = $derived(group.events.some((e) => e.kind === "decision"));
  const pending = $derived(!row && app.state && app.state.pending.n === group.n ? app.state.pending : null);
  const where = $derived(row ?? pending);
  const bad = $derived(row !== undefined && (row.respects === false || row.respects_policies === false));
  const tone = $derived(!decided ? "open" : bad ? "problem" : requestProblem(group, row) ? "ask" : "");
  const reading = $derived(group.events.find((e) => e.kind === "reading"));
  const v = $derived(row ? verdict(row) : null);

  function open(event: MouseEvent) {
    if ((event.target as HTMLElement).closest("button, summary, details")) return;
    if (row) void app.pinRequest(group.n!);
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<article class="card {tone}" class:pinned={app.pin === group.n} class:clickable={!!row} onclick={open}
         title={row ? "show this request on the map" : undefined}>
  <div class="ch">
    <span class="id">#{group.n}</span>
    <span class="what">{#if where}{where.source} → {where.destination} · {where.bit_rate}G{/if}</span>
    <span class="t">{group.events[0].hour.toFixed(1)} h</span>
  </div>
  {#if ins}
    <div class="quote">{ins.detail}</div>
    <div>
      {#if ins.data?.lang}<span class="tag lang">{ins.data.lang}</span>{/if}
      <span class="tag">{KIND[ins.data?.kind] ?? ins.data?.kind ?? ""}</span>
    </div>
  {/if}
  <ul class="steps">
    {#each group.events as e (e.n)}
      {#if e.kind === "reading"}
        {#if e.title.startsWith("readers agree")}
          <li><span class="ic good">✓</span><span>Readers agree: <b>{e.title.replace("readers agree: ", "")}</b>{#if e.data?.seconds}<span class="dim"> ({e.data.seconds[0]} s)</span>{/if}</span></li>
        {:else}
          <li><span class="ic warn">≠</span><span>Readers differ: {e.detail}</span></li>
        {/if}
      {:else if e.kind === "provisional"}
        <li><span class="ic dim">·</span><span>{e.title}: {e.detail}</span></li>
      {:else if e.kind === "question"}
        <li><span class="ic warn">?</span><span><b>{e.title.replace("readers differ: ", "")}</b>{#if e.detail}<span class="dim"> ({e.detail})</span>{/if}</span></li>
      {:else if e.kind === "answer"}
        <li><span class="ic good">✓</span><span>You settled it: <b>{e.detail}</b></span></li>
      {:else if e.kind === "decider"}
        <li><span class="ic decider">◆</span><span>{e.title}: {e.detail}</span></li>
      {:else if e.kind === "guard"}
        <li><span class="ic warn">⛨</span><span>Guard: the decider's route broke the line and was replaced <span class="dim">({e.detail})</span></span></li>
      {:else if e.kind === "unread"}
        <li><span class="ic bad">!</span><span>{e.title}</span></li>
      {/if}
    {/each}
  </ul>
  {#if row}
    <div class="route">{#if row.blocked}<span class="warn">rejected</span>{:else}{routeText(row.route)}{/if}</div>
    <div class="foot">
      <span class="dim who">{row.who}{row.slot !== null ? ` · slot ${row.slot}` : ""}</span>
      {#if v}<span class="badge {v.tone}" title={v.title}>{v.text}</span>{/if}
      {#if row.respects_policies === false}<span class="badge no">breaks policy {row.broken.map((i) => "#" + i).join(" ")}</span>{/if}
      {#if row.asked}<span class="badge asked">asked</span>{/if}
      <button class="inspect" onclick={() => app.openInspector(group.n!)} title="the five candidate paths, why each was kept or dropped, and the spectrum">inspect</button>
    </div>
    {#if app.detail}
      <details>
        <summary>model lines</summary>
        <pre>{#if reading?.data?.lines}reader 1: {reading.data.lines[0]}
reader 2: {reading.data.lines[1]}
{/if}line applied: {row.effective}{#if row.meant}
what was meant: {row.meant}{/if}</pre>
        {#if row.tapi}<pre>{JSON.stringify(row.tapi, null, 1)}</pre>{/if}
      </details>
    {/if}
  {:else if group.events.some((e) => e.kind === "question") && app.state?.question}
    <div class="route warn">waiting for your answer →</div>
  {/if}
</article>

<style>
  .card { margin: 6px 0; padding: 9px 11px; border: 1px solid var(--line); border-left: 3px solid var(--cyan); border-radius: 8px; background: var(--panel); }
  .clickable { cursor: pointer; }
  .clickable:hover { background: var(--panel2); }
  .pinned { outline: 1px solid #ffffff99; }
  .problem { border-left-color: var(--red); background: #1a1013; }
  .problem:hover { background: #21141a; }
  .ask { border-left-color: var(--amber); }
  .open { border-left-style: dashed; border-left-color: var(--amber); }
  .ch { display: flex; gap: 8px; align-items: baseline; }
  .id { font-family: var(--mono); font-size: 11px; color: var(--dim); }
  .what { font-weight: 600; }
  .t { margin-left: auto; font-family: var(--mono); font-size: 10.5px; color: var(--dim); white-space: nowrap; }
  .quote { margin: 4px 0 2px; }
  .steps { margin: 6px 0 0; padding: 0; list-style: none; }
  .steps li { display: flex; gap: 7px; padding: 2px 0; color: var(--muted); font-size: 12px; }
  .steps li b { color: var(--ink); font-weight: 500; }
  .ic { width: 14px; flex: none; text-align: center; }
  .ic.decider { color: var(--violet); }
  .route { margin-top: 7px; padding-top: 6px; border-top: 1px solid var(--line); font-size: 12.5px; }
  .foot { display: flex; align-items: center; gap: 6px; margin-top: 4px; flex-wrap: wrap; }
  .who { font-size: 11.5px; margin-right: auto; }
  .inspect { padding: 1px 8px; font-size: 11px; border-radius: 999px; background: transparent; }
  details { margin-top: 6px; }
</style>
