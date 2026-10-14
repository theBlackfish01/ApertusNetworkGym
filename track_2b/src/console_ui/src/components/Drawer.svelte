<script lang="ts">
  // The bottom tabs: the audit trail, the policy report, the policies over time, and the metrics.
  import { routeText, scopeText } from "../lib/format";
  import { app, type Tab } from "../lib/store.svelte";
  import Metrics from "./Metrics.svelte";
  import PolicyTimeline from "./PolicyTimeline.svelte";

  const s = $derived(app.state!);
  const TABS: [Exclude<Tab, null>, string][] = [["audit", "Audit trail"], ["report", "Policy report"], ["timeline", "Policies over time"], ["metrics", "Metrics"]];
  const rows = $derived(s.audit.slice().reverse());
  function pick(tab: Exclude<Tab, null>) {
    app.tab = app.tab === tab ? null : tab;
  }
</script>

<div class="tabs" role="tablist" aria-label="details">
  {#each TABS as [key, label] (key)}
    <button role="tab" aria-selected={app.tab === key} class:on={app.tab === key} onclick={() => pick(key)}>
      {label}{#if key === "audit" && s.audit.length} ({s.audit.length}){/if}
    </button>
  {/each}
  <span class="hint">space: play · s: step · ←/→ on the timeline · Ctrl+K: commands</span>
</div>

{#if app.tab}
  <div class="drawer scroll" role="tabpanel">
    {#if app.tab === "audit"}
      <table>
        <thead><tr><th class="num">#</th><th class="num">h</th><th>Request</th><th>Instruction</th><th>Line applied</th><th>Policies</th>
          <th>Decided by</th><th>Decision</th><th>Instr.</th><th>Policies</th></tr></thead>
        <tbody>
          {#each rows as r (r.n)}
            <tr class="clickable" class:pinned={app.pin === r.n} onclick={() => app.pinRequest(r.n)} ondblclick={() => app.openInspector(r.n)}
                tabindex="0" onkeydown={(e) => { if (e.key === "Enter") app.openInspector(r.n); else if (e.key === " ") { e.preventDefault(); void app.pinRequest(r.n); } }}
                title="click or space: show on the map · double-click or Enter: inspect">
              <td class="num">{r.n}</td><td class="num">{r.hour}</td><td>{r.source} → {r.destination}, {r.bit_rate} G</td>
              <td>{#if r.instruction === "none"}<span class="dim">—</span>{:else}{r.instruction}{/if}</td>
              <td class="mono">{r.effective}</td>
              <td>{#if r.policies.length}{r.policies.map((i) => "#" + i).join(" ")}{:else}<span class="dim">—</span>{/if}</td>
              <td>{r.who}{#if r.asked}<span class="warn"> · asked</span>{/if}</td>
              <td>{#if r.blocked}<span class="warn">rejected</span>{:else}{routeText(r.route)}, slot {r.slot}{/if}{#if r.invalid}<span class="bad"> invalid</span>{/if}</td>
              <td>{#if r.respects === null}<span class="dim">—</span>{:else if r.respects}<span class="good">yes</span>{:else}<span class="bad">no</span>{/if}</td>
              <td>{#if r.respects_policies === null}<span class="dim">—</span>{:else if r.respects_policies}<span class="good">yes</span>{:else}<span class="bad">no</span>{/if}</td>
            </tr>
          {:else}<tr><td colspan="10" class="dim">No request decided yet.</td></tr>{/each}
        </tbody>
      </table>
    {:else if app.tab === "report"}
      <table>
        <thead><tr><th class="num">#</th><th>Policy</th><th>Line</th><th>Scope</th><th>Holds</th><th class="num">Covered</th><th class="num">Changed</th>
          <th class="num">Rejected</th><th class="num">Violations</th><th></th></tr></thead>
        <tbody>
          {#each s.policies.slice().reverse() as p (p.id)}
            <tr class:gone={!p.active} onmouseenter={() => (app.hover = p.active ? p.id : null)} onmouseleave={() => (app.hover = null)}>
              <td class="num">{p.id}</td><td>{p.text}</td><td class="mono">{p.line}</td><td>{scopeText(p.scope)}</td>
              <td>{p.until === null ? "until withdrawn" : `${p.until} h (until hour ${p.expires})`}{p.active ? "" : " · ended"}</td>
              <td class="num">{p.in_scope}</td><td class="num">{p.changed}</td><td class="num">{p.rejected}</td><td class="num">{p.violations}</td>
              <td>{#if p.active}<button onclick={() => app.withdraw(p.id)}>Withdraw</button>{/if}</td>
            </tr>
          {:else}<tr><td colspan="10" class="dim">No policy yet.</td></tr>{/each}
        </tbody>
      </table>
    {:else if app.tab === "timeline"}
      <PolicyTimeline />
    {:else}
      <Metrics />
    {/if}
  </div>
{/if}

<style>
  .tabs { display: flex; gap: 2px; padding: 0 12px; border-top: 1px solid var(--line); flex-wrap: wrap; }
  .tabs button { border: 0; border-radius: 0; background: transparent; color: var(--dim); font-size: 11px; letter-spacing: 0.07em; text-transform: uppercase;
                 padding: 7px 10px; border-bottom: 2px solid transparent; }
  .tabs button.on { color: var(--ink); border-bottom-color: var(--cyan); }
  .hint { margin-left: auto; color: var(--dim); font-size: 11px; align-self: center; }
  .drawer { max-height: min(36vh, 320px); overflow: auto; padding: 0 12px 10px; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { color: var(--dim); font-weight: 600; position: sticky; top: 0; background: var(--panel); }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  tr.clickable { cursor: pointer; }
  tr.clickable:hover td, tr.pinned td { background: var(--panel2); }
  tr.gone td { color: var(--dim); }
  @media (max-width: 760px), (pointer: coarse) { .hint { display: none; } } /* keyboard hints mean nothing on a phone */
  @media (max-width: 760px) { .tabs { flex-wrap: nowrap; overflow-x: auto; padding: 0 6px; } .tabs button { white-space: nowrap; padding: 7px 8px; } }
</style>
