<script lang="ts">
  import { KIND, holds, remaining, routeText, scopeText, verdict } from "../lib/format";
  import { app } from "../lib/store.svelte";
  import QuestionCard from "./QuestionCard.svelte";

  const s = $derived(app.state!);
  const last = $derived(app.lastDecision);
  const active = $derived(s.policies.filter((p) => p.active).slice().reverse());
  const v = $derived(last ? verdict(last) : null);
</script>

<aside class="rail scroll" aria-label="the next request, the last decision and the policies in force">
  {#if s.question}<QuestionCard q={s.question} />{/if}

  <h2>Next request</h2>
  <div class="box">
    <h3>#{s.pending.n} · {s.pending.source} → {s.pending.destination}, {s.pending.bit_rate} Gb/s</h3>
    {#if s.pending.instruction.text === "none"}
      <div class="dim">no instruction with this request</div>
    {:else}
      <div class="quote">{s.pending.instruction.text}</div>
      <div>
        {#if s.pending.instruction.lang}<span class="tag lang">{s.pending.instruction.lang}</span>{/if}
        <span class="tag">{s.pending.instruction.typed ? "typed by you" : (KIND[s.pending.instruction.kind] ?? s.pending.instruction.kind)}</span>
      </div>
    {/if}
    <div class="kv">
      <span>candidates</span><span>{s.pending.paths.length} paths <button class="link" onclick={() => app.openInspector(s.pending.n)}>show</button></span>
      <span>covered by</span>
      <span>
        {#each s.in_force.covering as id (id)}
          <span class="tag pid" role="note" onmouseenter={() => (app.hover = id)} onmouseleave={() => (app.hover = null)}>#{id}</span>
        {:else}<span class="dim">no policy</span>{/each}
      </span>
    </div>
  </div>

  <h2>Last decision</h2>
  <div class="box">
    {#if last}
      <h3>#{last.n} · {last.source} → {last.destination}, {last.bit_rate} Gb/s</h3>
      <div class="route">{#if last.blocked}<span class="warn">rejected</span>{:else}{routeText(last.route)}{/if}</div>
      {#if v}<span class="badge {v.tone}" title={v.title}>{v.text}</span>{/if}
      <div class="kv">
        <span>decided by</span><span>{last.who}{last.slot !== null ? `, slot ${last.slot}` : ""}</span>
        {#if last.instruction !== "none"}<span>instruction</span><span>{last.instruction}</span>{/if}
      </div>
      {#if app.detail}<div class="mono">{last.effective}</div>{/if}
      <div class="row">
        <button onclick={() => app.openInspector(last.n)}>Inspect</button>
        <button class="ghost" onclick={() => app.pinRequest(last.n)}>{app.pin === last.n ? "Back to live" : "Show on the map"}</button>
      </div>
    {:else}
      <div class="dim">No request decided yet.</div>
    {/if}
  </div>

  <h2>Policies in force · {active.length}</h2>
  <div class="plist">
    {#each active as p (p.id)}
      {@const left = remaining(p, s.now)}
      <div class="prow" role="group" title={p.text} onmouseenter={() => (app.hover = p.id)} onmouseleave={() => (app.hover = null)}>
        <div class="top">
          <span class="num">#{p.id}</span><span class="rb">{p.readback}</span>
          <button class="x" onclick={() => app.withdraw(p.id)} title="withdraw policy #{p.id}" aria-label="withdraw policy {p.id}">×</button>
        </div>
        <div class="meta">
          <span>{scopeText(p.scope)}</span><span>{holds(p, s.now)}</span>
          <span>covered {p.in_scope} · changed {p.changed}{#if p.violations}<span class="bad"> · violations {p.violations}</span>{/if}</span>
        </div>
        {#if left !== null}<div class="bar"><i style:width="{(100 * left).toFixed(0)}%"></i></div>{/if}
        {#if app.detail}<div class="mono">{p.line}</div>{/if}
      </div>
    {:else}
      <div class="box dim">None yet. Type one below, or let them arrive (Stream ▾).</div>
    {/each}
  </div>
</aside>

<style>
  .rail { border-left: 1px solid var(--line); overflow: auto; min-height: 0; padding-bottom: 12px; }
  h2 { padding: 11px 12px 7px; }
  .box { margin: 0 12px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 9px; background: var(--panel); }
  h3 { margin: 0 0 4px; font-size: 13px; font-weight: 600; }
  .quote { margin: 3px 0 4px; }
  .route { margin: 3px 0 6px; }
  .kv { display: grid; grid-template-columns: 88px 1fr; gap: 3px 8px; margin-top: 7px; font-size: 12px; }
  .kv > span:nth-child(odd) { color: var(--dim); }
  .row { display: flex; gap: 6px; margin-top: 9px; flex-wrap: wrap; }
  .link { padding: 0 6px; font-size: 11px; background: transparent; border-color: transparent; color: var(--cyan); }
  .pid { color: var(--violet); cursor: default; }
  .plist { margin: 0 12px; }
  .prow { padding: 8px 10px 9px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); margin-bottom: 6px; }
  .prow:hover { border-color: var(--violet); background: #151229; }
  .top { display: flex; gap: 7px; align-items: baseline; }
  .num { font-family: var(--mono); font-size: 11px; color: var(--violet); }
  .rb { flex: 1; }
  .x { padding: 0 6px; font-size: 11px; line-height: 18px; background: transparent; color: var(--dim); }
  .meta { display: flex; gap: 8px; font-size: 11px; color: var(--dim); margin-top: 4px; flex-wrap: wrap; }
  .bar { height: 3px; background: var(--line); border-radius: 2px; margin-top: 6px; overflow: hidden; }
  .bar i { display: block; height: 100%; background: var(--violet); }
  .mono { margin-top: 5px; }
</style>
