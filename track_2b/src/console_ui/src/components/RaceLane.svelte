<script lang="ts">
  // One method in the race: its network, its route for the request just decided, and its record.
  import { pct, routeText } from "../lib/format";
  import type { NodeRow, RaceLane, RaceRequest } from "../lib/types";
  import NetworkMap from "./NetworkMap.svelte";

  let { lane, nodes, request, color }: { lane: RaceLane; nodes: NodeRow[]; request: RaceRequest | null; color: string } = $props();
  const out = $derived(lane.last);
  const inside = $derived(lane.classes["inside the language"]);
  const never = $derived(lane.classes["types never shown"]);
</script>

<article class="lane" style:--lane={color}>
  <div class="head">
    <span class="swatch"></span>
    <h3>{lane.label}</h3>
    <span class="rate" title="violations, share of the requests decided">{pct(lane.violations, lane.served)}</span>
  </div>
  <div class="what">{lane.what}</div>
  <div class="map">
    <NetworkMap
      {nodes}
      links={lane.links}
      route={out?.route ?? null}
      routeTone={out?.violation ? "bad" : "live"}
      pending={request ? [request.source, request.destination] : []}
      compact
      label="{lane.label}: the network and its last route"
    />
  </div>
  <div class="last">
    {#if out}
      {#if out.invalid}<span class="badge no">invalid answer: first fit stood in</span>
      {:else if out.violation}<span class="badge no">breaks the instruction</span>
      {:else if request?.class === "nothing to apply"}<span class="badge na">nothing to respect</span>
      {:else}<span class="badge ok">respects it</span>{/if}
      <span class="route">{routeText(out.route)}</span>
      <span class="dim who">{out.who}</span>
    {:else}
      <span class="dim">waiting for the first request</span>
    {/if}
  </div>
  <div class="stats">
    <span><b>{lane.violations}</b> violations</span>
    <span><b>{pct(lane.rejected, lane.served)}</b> rejected</span>
    <span title="violations inside the policy language">inside the language <b>{pct(inside?.violations ?? 0, inside?.n ?? 0)}</b></span>
    <span title="violations on instruction types no component was shown">types never shown <b>{pct(never?.violations ?? 0, never?.n ?? 0)}</b></span>
  </div>
  {#if lane.same_as_stored !== null}
    <div class="check" class:good={lane.same_as_stored} class:bad={!lane.same_as_stored}>
      {lane.same_as_stored ? `✓ the same as the stored evaluation run (${lane.stored_violations} violations)` : `✗ differs from the stored run (${lane.stored_violations} violations)`}
    </div>
  {/if}
</article>

<style>
  .lane { display: flex; flex-direction: column; min-height: 0; padding: 9px 11px; border: 1px solid var(--line); border-top: 3px solid var(--lane);
          border-radius: 9px; background: var(--panel); }
  .head { display: flex; align-items: center; gap: 8px; }
  .swatch { width: 10px; height: 10px; border-radius: 50%; background: var(--lane); }
  h3 { margin: 0; font-size: 13.5px; }
  .rate { margin-left: auto; font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .what { font-size: 11px; color: var(--dim); margin: 1px 0 4px; min-height: 2.6em; }
  .map { position: relative; flex: 1; min-height: 120px; }
  .last { display: flex; align-items: center; gap: 6px; margin-top: 4px; font-size: 11.5px; flex-wrap: wrap; min-height: 22px; }
  .route { color: var(--muted); }
  .who { margin-left: auto; }
  .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 1px 10px; margin-top: 6px; font-size: 11px; color: var(--dim); }
  .stats b { color: var(--ink); font-variant-numeric: tabular-nums; }
  .check { margin-top: 6px; font-size: 11px; }
</style>
