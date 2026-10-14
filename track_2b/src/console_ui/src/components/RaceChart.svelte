<script lang="ts">
  // Violations so far, as a share of the requests decided, for each method along the stream. Drawn at
  // the panel's own size in pixels, so the text stays legible; the end labels are pushed apart when
  // two methods end close together.
  import { pct } from "../lib/format";
  import type { RaceLane } from "../lib/types";

  let { lanes, every, colors, window }: { lanes: RaceLane[]; every: number; colors: Record<string, string>; window: number } = $props();
  let width = $state(700), height = $state(190);
  const W = $derived(Math.max(360, width)), H = $derived(Math.max(150, height));
  const L = 38, R = 170, T = 10, B = 22, GAP = 14;
  const shares = $derived(lanes.map((lane) => lane.series.map((v, i) => v / ((i + 1) * every))));
  const top = $derived(Math.max(0.1, ...shares.flat().slice(3)) * 1.1);
  const x = (i: number) => L + (((i + 1) * every) / window) * (W - L - R);
  const y = (v: number) => T + (1 - Math.min(v, top) / top) * (H - T - B);
  const ends = $derived.by(() => {
    const out = lanes
      .map((lane, k) => ({ lane, pts: shares[k] }))
      .filter((e) => e.pts.length > 1)
      .map((e) => ({
        key: e.lane.key, label: e.lane.label, x: x(e.pts.length - 1), y: y(e.pts[e.pts.length - 1]), ly: 0,
        share: pct(e.lane.series[e.pts.length - 1], e.pts.length * every), // the lane's own rounding, so the two agree
      }))
      .sort((a, b) => a.y - b.y);
    for (let i = 0; i < out.length; i++) out[i].ly = Math.max(out[i].y, i ? out[i - 1].ly + GAP : T);
    const over = out.length ? out[out.length - 1].ly - (H - B) : 0;
    if (over > 0) for (const e of out) e.ly -= over;
    return out;
  });
</script>

<div class="frame" bind:clientWidth={width} bind:clientHeight={height}>
  <svg viewBox="0 0 {W} {H}" width={W} height={H} role="img" aria-label="violations so far, as a share of the requests decided, for each method">
    {#each [0, top / 2, top] as v (v)}
      <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} class="grid" />
      <text x={L - 6} y={y(v) + 3} class="axis">{(100 * v).toFixed(0)}%</text>
    {/each}
    {#each [0, 500, 1000, 1500, 2000] as t (t)}
      <text x={L + (t / window) * (W - L - R)} y={H - 6} class="axis mid">{t}</text>
    {/each}
    {#each lanes as lane, k (lane.key)}
      {@const pts = shares[k]}
      {#if pts.length > 1}
        <polyline fill="none" stroke={colors[lane.key]} stroke-width="2" stroke-linejoin="round"
                  points={pts.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ")} />
      {/if}
    {/each}
    {#each ends as e (e.key)}
      <circle cx={e.x} cy={e.y} r="3.5" fill={colors[e.key]} />
      {#if Math.abs(e.ly - e.y) > 1}<line x1={e.x + 4} y1={e.y} x2={e.x + 10} y2={e.ly} class="leader" />{/if}
      <text x={e.x + 12} y={e.ly + 4} class="end">{e.label} <tspan class="v">{e.share}</tspan></text>
    {/each}
  </svg>
</div>

<style>
  .frame { position: relative; flex: 1; min-height: 150px; }
  svg { position: absolute; inset: 0; display: block; }
  .grid { stroke: var(--line); }
  .axis { font-size: 10.5px; fill: var(--dim); text-anchor: end; }
  .axis.mid { text-anchor: middle; }
  .leader { stroke: var(--line2); }
  .end { font-size: 11.5px; font-weight: 600; fill: var(--ink); }
  .end .v { fill: var(--muted); font-weight: 500; }
</style>
