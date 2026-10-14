<script lang="ts">
  // Every policy as a bar over simulated time: from the hour it came into force to its expiry, its
  // withdrawal, or now; coloured by what it covers. Scope and lifetime at a glance.
  import { scopeText } from "../lib/format";
  import { app } from "../lib/store.svelte";

  const s = $derived(app.state!);
  const policies = $derived(s.policies.slice().sort((a, b) => a.id - b.id));
  const start = $derived(Math.min(s.now, ...policies.map((p) => p.created)));
  const end = $derived(Math.max(s.now + 0.5, ...policies.map((p) => (p.active ? (p.expires ?? s.now) : (p.ended ?? p.expires ?? s.now)))));
  const W = 1000, ROW = 22, LEFT = 300;
  const x = (h: number) => LEFT + ((h - start) / Math.max(end - start, 0.01)) * (W - LEFT - 10);
  function tone(scope: string): string {
    const kind = scope.split(":")[0];
    return kind === "rate" ? "rate" : kind === "from" || kind === "to" ? "place" : "all";
  }
  const ticks = $derived.by(() => {
    const span = end - start, step = span > 24 ? 6 : span > 8 ? 2 : span > 3 ? 1 : 0.5;
    const out: number[] = [];
    for (let h = Math.ceil(start / step) * step; h <= end; h += step) out.push(h);
    return out;
  });
</script>

{#if policies.length === 0}
  <div class="dim pad">No policy yet.</div>
{:else}
  <svg viewBox="0 0 {W} {(policies.length + 1) * ROW + 8}" role="img" aria-label="policies over simulated time">
    <defs>
      <linearGradient id="openFade"><stop offset="0.8" stop-color="#fff" /><stop offset="1" stop-color="#fff" stop-opacity="0.1" /></linearGradient>
      <mask id="openMask" maskContentUnits="objectBoundingBox"><rect width="1" height="1" fill="url(#openFade)" /></mask>
    </defs>
    {#each ticks as t (t)}
      <line x1={x(t)} x2={x(t)} y1="0" y2={(policies.length + 1) * ROW} class="tick" />
      <text x={x(t)} y={(policies.length + 1) * ROW + 6} class="tl">{t.toFixed(t % 1 ? 1 : 0)} h</text>
    {/each}
    <line x1={x(s.now)} x2={x(s.now)} y1="0" y2={(policies.length + 1) * ROW} class="now" />
    {#each policies as p, i (p.id)}
      {@const y = i * ROW + 6}
      {@const stop = p.active ? (p.expires ?? end) : (p.ended ?? p.expires ?? s.now)}
      {@const right = x(stop) > W - 140}
      {@const wide = x(stop) - x(p.created) > 170}
      <g class="row" role="listitem" onmouseenter={() => (app.hover = p.active ? p.id : null)} onmouseleave={() => (app.hover = null)}>
        <text x="4" y={y + 12} class="name" class:gone={!p.active}>#{p.id} {p.readback.length > 44 ? p.readback.slice(0, 43) + "…" : p.readback}</text>
        <rect x={x(p.created)} y={y + 2} width={Math.max(2, x(stop) - x(p.created))} height="13" rx="3" class="bar {tone(p.scope)}" class:gone={!p.active}
              mask={p.active && p.expires === null ? "url(#openMask)" : null} />
        <text x={!right ? x(stop) + 5 : wide ? x(p.created) + 8 : x(p.created) - 6} y={y + 12} class="meta" class:inside={right && wide} class:before={right && !wide}>{scopeText(p.scope)}{p.active ? "" : p.ended !== null && p.expires !== null && p.ended < p.expires ? " · withdrawn" : " · ended"}</text>
        <title>{p.text}</title>
      </g>
    {/each}
  </svg>
  <div class="dim key"><i class="all"></i>all requests <i class="rate"></i>one bit rate <i class="place"></i>from or to a node · faded: no longer in force · white line: now · a bar that fades out holds until withdrawn</div>
{/if}

<style>
  svg { width: 100%; display: block; margin-top: 6px; }
  .pad { padding: 10px; }
  .tick { stroke: var(--line); }
  .now { stroke: #ffffffaa; stroke-dasharray: 3 3; }
  .tl { font-size: 10px; fill: var(--dim); text-anchor: middle; }
  .name { font-size: 11px; fill: var(--ink); }
  .name.gone { fill: var(--dim); }
  .meta { font-size: 10px; fill: var(--dim); }
  .bar.all { fill: var(--violet); }
  .bar.rate { fill: #c88bff; }
  .bar.place { fill: #7b8cff; }
  .bar.gone { opacity: 0.32; }
  .meta.inside { fill: #0b0f17; font-weight: 600; }
  .meta.before { text-anchor: end; }
  .row:hover .bar { filter: brightness(1.25); }
  .key { font-size: 11px; margin-top: 4px; }
  .key i { display: inline-block; width: 12px; height: 8px; margin: 0 4px 0 10px; border-radius: 2px; vertical-align: middle; }
  .key i.all { background: var(--violet); } .key i.rate { background: #c88bff; } .key i.place { background: #7b8cff; }
</style>
