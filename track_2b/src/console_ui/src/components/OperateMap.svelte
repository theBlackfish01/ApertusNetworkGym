<script lang="ts">
  // The operate view's map: the network now, or as it was for a pinned request; a hovered policy lit up.
  import { linkKey } from "../lib/geo";
  import { app } from "../lib/store.svelte";
  import NetworkMap from "./NetworkMap.svelte";

  const s = $derived(app.state!);
  const spec = $derived(s.in_force.spec ?? { avoid: [], prefer: [], status: "ok" });
  const hot = $derived(app.hover !== null ? s.policies.find((p) => p.id === app.hover)?.spec : undefined);
  const links = $derived(
    app.pinDetail?.used ? s.links.map((l, i) => ({ ...l, used: app.pinDetail!.used![i] ?? l.used })) : s.links,
  );
  const pinRow = $derived(app.pin !== null ? app.auditByN.get(app.pin) : undefined);
</script>

<div class="om">
<div class="canvas">
<NetworkMap
  nodes={s.nodes}
  {links}
  avoidLinks={new Set((spec.avoid ?? []).map(([a, b]) => linkKey(a, b)))}
  avoidNodes={new Set(spec.nodes ?? [])}
  via={new Set(spec.via ?? [])}
  route={app.pin !== null ? (pinRow?.route ?? app.pinDetail?.route ?? null) : s.last_route}
  routeTone={app.pin !== null ? "past" : "live"}
  pending={app.pin !== null ? [] : [s.pending.source, s.pending.destination]}
  hotLinks={new Set((hot?.avoid ?? []).map(([a, b]) => linkKey(a, b)))}
  hotNodes={new Set(hot?.nodes ?? [])}
  hotVia={new Set(hot?.via ?? [])}
  animate={app.animate}
/>

{#if app.pin !== null}
  <div class="note">
    showing request #{app.pin} as it was decided{pinRow?.blocked ? ": rejected" : ""}
    <button onclick={() => app.unpin()}>back to live</button>
    <button onclick={() => app.openInspector(app.pin!)}>inspect</button>
  </div>
{:else if app.hover !== null}
  <div class="note">policy #{app.hover} highlighted</div>
{/if}
</div>

<div class="legend" aria-hidden="true">
  <span><i style="background:#5f7fae"></i>link, brighter = more occupied</span>
  <span><i style="background:var(--cyan)"></i>route just set up</span>
  <span><i style="background:#fff"></i>a past request, when one is shown</span>
  <span><i style="background:var(--red)"></i>avoided by a policy or the instruction</span>
  <span><i class="dot" style="background:var(--green)"></i>must pass through</span>
  <span><i class="dot" style="background:var(--amber)"></i>next request's end points</span>
</div>
</div>

<style>
  .note { position: absolute; right: 12px; top: 8px; display: flex; align-items: center; gap: 6px; padding: 4px 6px 4px 12px; border: 1px solid var(--line2);
          border-radius: 999px; background: var(--panel2); font-size: 11.5px; color: var(--muted); }
  .note button { padding: 0 9px; font-size: 11px; line-height: 20px; border-radius: 999px; }
  .om { position: absolute; inset: 0; display: flex; flex-direction: column; }
  .canvas { position: relative; flex: 1; min-height: 0; }
  .legend { display: flex; flex-wrap: wrap; justify-content: center; gap: 2px 16px; padding: 3px 12px 6px; color: var(--muted); font-size: 10.5px; }
  .legend i { display: inline-block; width: 16px; height: 3px; margin-right: 6px; vertical-align: middle; border-radius: 2px; }
  .legend i.dot { width: 8px; height: 8px; border-radius: 50%; margin: 0 10px 0 4px; }
</style>
