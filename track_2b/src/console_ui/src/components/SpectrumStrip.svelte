<script lang="ts">
  // One link's 320 spectrum slots at the moment of the decision: in use (grey), free (dark), and the
  // block the decision took (cyan, with a caret above it, since one slot is a fraction of a pixel wide).
  // Runs of equal state are drawn as one rectangle.
  import type { Strip } from "../lib/types";

  let { strip }: { strip: Strip } = $props();
  const runs = $derived.by(() => {
    const out: { start: number; length: number; used: boolean }[] = [];
    const s = strip.occupied;
    let start = 0;
    for (let i = 1; i <= s.length; i++) {
      if (i === s.length || s[i] !== s[start]) {
        out.push({ start, length: i - start, used: s[start] === "1" });
        start = i;
      }
    }
    return out;
  });
  const free = $derived([...strip.occupied].filter((c) => c === "0").length);
  const total = $derived(strip.occupied.length);
  const took = $derived(strip.block[1] > 0);
  const caret = $derived(took ? (100 * (strip.block[0] + strip.block[1] / 2)) / total : 0);
  const slots = $derived(strip.block[1] === 1 ? `slot ${strip.block[0]}` : `slots ${strip.block[0]}–${strip.block[0] + strip.block[1] - 1}`);
</script>

<div class="strip">
  <div class="label"><span>{strip.a} – {strip.b}</span><span class="dim">{#if took}took {slots} · {/if}{free} of {total} free</span></div>
  <div class="bar">
  {#if took}<span class="caret" style:left="{caret}%" aria-hidden="true"></span>{/if}
  <svg viewBox="0 0 {total} 10" preserveAspectRatio="none" role="img" aria-label="spectrum of {strip.a} to {strip.b}: {free} of {total} slots free">
    {#each runs as r (r.start)}
      <rect x={r.start} y="0" width={r.length} height="10" class={r.used ? "used" : "free"} />
    {/each}
    {#if strip.block[1] > 0}
      <rect x={strip.block[0]} y="0" width={strip.block[1]} height="10" class="taken" />
    {/if}
  </svg>
  </div>
</div>

<style>
  .strip { margin: 4px 0 7px; }
  .label { display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 2px; }
  .bar { position: relative; padding-top: 5px; }
  .caret { position: absolute; top: 0; width: 0; height: 0; margin-left: -4px; border: 4px solid transparent; border-bottom: 0; border-top: 5px solid var(--cyan); }
  svg { width: 100%; height: 12px; display: block; border-radius: 2px; overflow: hidden; }
  .used { fill: #4a5670; }
  .free { fill: #121826; }
  .taken { fill: var(--cyan); }
</style>
