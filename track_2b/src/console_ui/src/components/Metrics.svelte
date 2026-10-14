<script lang="ts">
  // Shares over the last 50 requests, along the stream: violations, rejections, questions, decisions
  // by the decider. Trends, not only totals.
  import { app } from "../lib/store.svelte";

  const s = $derived(app.state!);
  // The chart is drawn at the drawer's own width in pixels, so its height and its text stay fixed.
  const WINDOW = 50, H = 140, PAD = 28;
  let width = $state(1000);
  const W = $derived(Math.max(320, width));
  const SERIES = [
    { key: "violation", label: "violations", color: "var(--red)" },
    { key: "rejected", label: "rejected", color: "#6f7a92" },
    { key: "asked", label: "questions", color: "var(--amber)" },
    { key: "decider", label: "to the decider", color: "var(--cyan)" }, // not orange: next to the red it fails the colour-vision check
  ] as const;
  const n = $derived(s.series.violation.length);
  const lines = $derived.by(() => {
    return SERIES.map((series) => {
      const bits = s.series[series.key];
      let sum = 0;
      const shares: number[] = [];
      for (let i = 0; i < bits.length; i++) {
        sum += bits[i] === "1" ? 1 : 0;
        if (i >= WINDOW) sum -= bits[i - WINDOW] === "1" ? 1 : 0;
        shares.push(sum / Math.min(i + 1, WINDOW));
      }
      return { ...series, shares, last: shares.length ? shares[shares.length - 1] : 0 };
    });
  });
  const top = $derived(Math.max(0.1, ...lines.flatMap((l) => l.shares)));
  const x = (i: number) => PAD + (n <= 1 ? 0 : (i / (n - 1)) * (W - 2 * PAD));
  const y = (v: number) => H - PAD + 6 - (v / top) * (H - PAD - 10);
</script>

{#if n < 2}
  <div class="dim pad">Decide a few requests to see the trends.</div>
{:else}
  <div class="legend">
    {#each lines as l (l.key)}<span><i style:background={l.color}></i>{l.label} <b>{(100 * l.last).toFixed(0)}%</b></span>{/each}
    <span class="dim">share of the last {WINDOW} requests</span>
  </div>
  <div bind:clientWidth={width}>
  <svg viewBox="0 0 {W} {H}" height={H} role="img" aria-label="shares over the last 50 requests along the stream">
    {#each [0, top / 2, top] as v (v)}
      <line x1={PAD} x2={W - PAD} y1={y(v)} y2={y(v)} class="grid" />
      <text x={PAD - 6} y={y(v) + 3} class="axis">{(100 * v).toFixed(0)}%</text>
    {/each}
    {#each lines as l (l.key)}
      <polyline fill="none" stroke={l.color} stroke-width="1.8" points={l.shares.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ")} />
    {/each}
    <text x={PAD} y={H - 4} class="axis start">request 1</text>
    <text x={W - PAD} y={H - 4} class="axis end">request {n}</text>
  </svg>
  </div>
{/if}

<style>
  .pad { padding: 10px; }
  .legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 11.5px; color: var(--muted); margin: 8px 0 2px; }
  .legend i { display: inline-block; width: 14px; height: 3px; margin-right: 5px; vertical-align: middle; border-radius: 2px; }
  .legend b { color: var(--ink); }
  svg { width: 100%; display: block; }
  .grid { stroke: var(--line); }
  .axis { font-size: 10px; fill: var(--dim); text-anchor: end; }
  .axis.start { text-anchor: start; }
  .axis.end { text-anchor: end; }
</style>
