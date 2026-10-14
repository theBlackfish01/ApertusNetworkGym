<script lang="ts">
  // One request, opened: the five candidate paths with why each was kept or dropped by the line that
  // was applied, the preferences that ranked the rest, the tie-break, who decided, and the spectrum
  // of the chosen route at the moment of the decision. The mechanism behind every verdict.
  import { get } from "../lib/api";
  import { lineDiff, lineFields, routeText, verdict } from "../lib/format";
  import { app } from "../lib/store.svelte";
  import type { RequestDetail } from "../lib/types";
  import SpectrumStrip from "./SpectrumStrip.svelte";

  let { n }: { n: number } = $props();
  let detail = $state<RequestDetail | null>(null);
  let failed = $state("");

  // A request not yet decided is fetched again once the stream has moved on, so that it shows its
  // decision when it gets one; a decided one is fetched once.
  const served = $derived(app.state?.stats.served ?? 0);
  const key = $derived(n > served ? `${n}:${served}` : `${n}`);
  let shownN = -1;
  $effect(() => {
    const want = key, at = n;
    if (at !== shownN) detail = null; // another request: clear; the same one, decided since: keep it until the answer
    shownN = at;
    failed = "";
    get<RequestDetail>(`/api/request?n=${at}`)
      .then((d) => {
        if (want !== key) return;
        if (d.error) failed = d.error;
        else detail = d;
      })
      .catch((e) => {
        if (want === key) failed = String(e);
      });
  });

  const row = $derived(detail?.row);
  const ins = $derived(row?.inspect);
  const v = $derived(row && detail?.decided && row.respects !== undefined ? verdict({ respects: row.respects ?? null, judged: row.judged ?? null }) : null);
  function close() {
    app.inspect = null; // Esc does the same (App.svelte, which knows whether a dialog or a field has the key)
  }
</script>

<aside class="inspector scroll" aria-label="request inspector">
  <div class="top">
    <h2>Request #{n}</h2>
    <span class="nav">
      <button class="ghost" disabled={n <= 1} onclick={() => (app.inspect = n - 1)} aria-label="previous request">‹</button>
      <button class="ghost" disabled={n > served} onclick={() => (app.inspect = n + 1)} aria-label="next request">›</button>
    </span>
    <button class="ghost close" onclick={close} title="close (Esc)" aria-label="close the inspector">×</button>
  </div>
  {#if failed}
    <div class="bad pad">{failed}</div>
  {:else if !row || (!ins && !detail?.pruned)}
    <div class="dim pad">reading…</div>
  {:else}
    <div class="pad">
      <h3>{row.source} → {row.destination}, {row.bit_rate} Gb/s</h3>
      {#if detail?.decided}
        <div class="route">{#if row.blocked}<span class="warn">rejected</span>{:else}{routeText(row.route)}{/if}</div>
        <div class="row">
          {#if v}<span class="badge {v.tone}" title={v.title}>{v.text}</span>{/if}
          {#if row.asked}<span class="badge asked">asked</span>{/if}
          <span class="dim small">{row.who}{row.slot !== null && row.slot !== undefined ? `, slot ${row.slot}` : ""}</span>
        </div>
        {#if row.instruction && row.instruction !== "none"}<div class="quote small">{row.instruction}</div>{/if}
      {:else}
        <div class="dim small">Not decided yet: the candidates under the policies in force now; the request's own instruction is read when it is decided.</div>
      {/if}

      <h4>The line applied</h4>
      {#if lineFields(row.effective ?? "").length}
        <div class="fields">{#each lineFields(row.effective ?? "") as [k, value] (k)}<span class="tag"><b>{k}</b> {value}</span>{/each}</div>
      {:else}
        <div class="dim small">nothing: no instruction applied and no policy covers this request</div>
      {/if}
      {#if detail?.decided && row.meant && row.meant !== row.effective}
        {@const diff = lineDiff(row.effective ?? "", row.meant)}
        <div class="small meant">
          <span class="warn">The recorded meaning differs:</span>
          {#each diff as [k, applied, meant] (k)}<span class="tag"><b>{k}</b> {meant} meant, {applied} applied</span>{/each}
          {#if diff.some(([k, , meant]) => k === "rest" && meant === "more")}
            <div class="dim">rest=more: part of the instruction lies outside the language, so the rule engine cannot enforce it.</div>
          {/if}
        </div>
      {/if}

      {#if !ins}
        <div class="dim small">The candidates and the spectrum are kept for the last 2,000 requests; this one is older.</div>
      {:else}
      <h4>The five candidates</h4>
      <ol class="cands">
        {#each ins.paths as p (p.index)}
          {@const chosen = ins.chosen === p.index}
          {@const kept = ins.admissible.includes(p.index)}
          <li class:chosen class:kept class:dropped={p.excluded.length > 0}>
            <div class="ph">
              <span class="num">{p.index}</span>
              <span class="nodes">{p.nodes.join(" → ")}</span>
              {#if chosen}<span class="badge ok">chosen</span>{:else if ins.engine === p.index && ins.chosen !== null}<span class="badge na">engine's choice</span>{/if}
            </div>
            <div class="facts">
              {p.hops} hops · {p.km.toLocaleString()} km · {p.free_slots} free slots ·
              {#if p.feasible}{p.modulation}, {p.slots_needed} slots, first free start {p.first_slot}{:else}<span class="bad">no room</span>{/if}
            </div>
            {#if p.excluded.length}
              <ul class="why">{#each p.excluded as w (w)}<li>✗ {w}</li>{/each}</ul>
            {:else}
              <div class="ok small">✓ meets the line</div>
            {/if}
          </li>
        {/each}
      </ol>

      <h4>How the rest was ranked</h4>
      <ul class="rank">
        <li>Constraints keep: {ins.paths.filter((p) => p.feasible && !p.excluded.length).map((p) => p.index).join(", ") || "none, so the request must be rejected"}</li>
        {#each ins.steps as st (st.by)}
          <li>{st.by}: {st.from.join(", ")} → <b>{st.kept.join(", ")}</b></li>
        {/each}
        {#if ins.admissible.length}<li class="dim">tie-break: {ins.tie_break}</li>{/if}
        {#if detail?.decided && ins.engine !== null && ins.chosen !== null && ins.engine !== ins.chosen}
          <li class="warn">The rule engine would take candidate {ins.engine}; the decision took {ins.chosen} ({row.who}).</li>
        {/if}
        {#if detail?.decided && ins.chosen === null && ins.admissible.length}
          <li class="warn">Rejected although candidate {ins.admissible.join(", ")} met the line.</li>
        {/if}
      </ul>

      {/if}

      {#if row.spectrum && row.spectrum.length}
        <h4>Spectrum of the chosen route, before it was set up</h4>
        {#each row.spectrum as strip (strip.a + strip.b)}<SpectrumStrip {strip} />{/each}
        <div class="dim small key"><i class="used"></i>in use <i class="free"></i>free <i class="taken"></i>the block this lightpath took</div>
      {/if}

      {#if app.detail && row.tapi}
        <details><summary>the line as a TAPI 2.1.3 constraint</summary><pre>{JSON.stringify(row.tapi, null, 1)}</pre></details>
      {/if}
      {#if detail?.decided}
        <div class="row end">
          <button onclick={() => app.pinRequest(n)}>{app.pin === n ? "Back to live on the map" : "Show on the map"}</button>
        </div>
      {/if}
    </div>
  {/if}
</aside>

<style>
  .inspector { position: absolute; top: 0; right: 0; bottom: 0; width: min(480px, 100%); z-index: 25; overflow: auto; background: var(--panel);
               border-left: 1px solid var(--line2); box-shadow: -14px 0 34px #0009; }
  .top { position: sticky; top: 0; display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: var(--panel); border-bottom: 1px solid var(--line); z-index: 1; }
  .nav { display: inline-flex; gap: 2px; }
  .nav button { padding: 0 8px; }
  .close { margin-left: auto; padding: 0 9px; }
  .pad { padding: 10px 14px 16px; }
  h3 { margin: 0 0 4px; font-size: 14px; }
  h4 { margin: 14px 0 6px; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--dim); font-weight: 650; }
  .route { margin-bottom: 5px; }
  .row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
  .row.end { margin-top: 14px; }
  .small { font-size: 12px; }
  .quote { margin-top: 6px; }
  .meant { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-top: 6px; }
  .meant .dim { flex-basis: 100%; }
  .fields { display: flex; flex-wrap: wrap; gap: 4px; }
  .fields b { color: var(--ink); font-weight: 600; }
  .cands { list-style: none; margin: 0; padding: 0; }
  .cands > li { padding: 7px 9px; margin-bottom: 5px; border: 1px solid var(--line); border-radius: 7px; background: var(--panel2); }
  .cands > li.dropped { opacity: 0.78; }
  .cands > li.kept { border-color: #1f4a3a; }
  .cands > li.chosen { border-color: var(--cyan); box-shadow: 0 0 0 1px #41c3ff44; opacity: 1; }
  .ph { display: flex; gap: 7px; align-items: baseline; }
  .num { font-family: var(--mono); color: var(--dim); }
  .nodes { flex: 1; font-size: 12.5px; }
  .facts { font-size: 11.5px; color: var(--muted); margin-top: 2px; }
  .why { list-style: none; margin: 4px 0 0; padding: 0; font-size: 11.5px; color: #ff9a9a; }
  .ok { color: var(--green); margin-top: 3px; }
  .rank { margin: 0; padding-left: 16px; font-size: 12px; color: var(--muted); }
  .rank li { margin: 2px 0; }
  .rank b { color: var(--ink); }
  .key i { display: inline-block; width: 10px; height: 8px; margin: 0 4px 0 8px; vertical-align: middle; border-radius: 1px; }
  .key i.used { background: #4a5670; } .key i.free { background: #121826; border: 1px solid var(--line2); } .key i.taken { background: var(--cyan); }
</style>
