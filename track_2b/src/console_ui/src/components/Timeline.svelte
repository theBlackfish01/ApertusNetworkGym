<script lang="ts">
  // Every decided request on one strip: violations (red), questions (amber), the guard (violet),
  // rejections (grey); a triangle where a policy came into force; the violation rate over the last
  // 50 requests as a thin line. Click (or arrow keys) shows that request on the map.
  import { app } from "../lib/store.svelte";

  const s = $derived(app.state!);
  const n = $derived(s.series.violation.length);
  const W = 1000, H = 46, TOP = 12;
  const x = (i: number) => (n <= 1 ? W / 2 : 6 + (i / (n - 1)) * (W - 12));
  const marks = $derived(
    Array.from({ length: n }, (_, i) => ({
      i,
      v: s.series.violation[i] === "1",
      r: s.series.rejected[i] === "1",
      a: s.series.asked[i] === "1",
      g: s.series.guard[i] === "1",
    })).filter((m) => m.v || m.r || m.a || m.g),
  );
  const arrivals = $derived(
    s.feed.filter((e) => e.kind === "policy_added").map((e) => ({ at: Math.min(Math.max(e.request - 1, 0), Math.max(n - 1, 0)), id: e.data?.policy as number })),
  );
  const rate = $derived.by(() => {
    const out: string[] = [];
    let sum = 0;
    for (let i = 0; i < n; i++) {
      sum += s.series.violation[i] === "1" ? 1 : 0;
      if (i >= 50) sum -= s.series.violation[i - 50] === "1" ? 1 : 0;
      const share = sum / Math.min(i + 1, 50);
      out.push(`${x(i).toFixed(1)},${(H - 3 - share * (H - TOP - 6)).toFixed(1)}`);
    }
    return out.join(" ");
  });
  let hoverAt = $state<number | null>(null);
  let box: SVGSVGElement | undefined = $state();

  function at(event: MouseEvent): number | null {
    if (!box || n === 0) return null;
    const r = box.getBoundingClientRect();
    const i = Math.round((((event.clientX - r.left) / r.width) * W - 6) / ((W - 12) / Math.max(n - 1, 1)));
    return Math.max(0, Math.min(n - 1, i));
  }
  function key(event: KeyboardEvent) {
    if (!n) return;
    const current = (app.pin ?? n + 1) - 1;
    if (event.key === "ArrowLeft") {
      if (app.pin !== 1) void app.pinRequest(Math.max(1, current)); // at the first request: stay (pinning it again would un-pin)
    }
    else if (event.key === "ArrowRight" && app.pin !== null) {
      if (app.pin >= n) app.unpin();
      else void app.pinRequest(app.pin + 1);
    } else return;
    event.preventDefault();
  }
</script>

<div class="timeline">
  <div class="head">
    <h2>Timeline</h2>
    <span class="dim">{n ? `${n} requests` : "no request decided yet"}</span>
    <span class="keys">
      <i class="v"></i>violation <i class="a"></i>question <i class="g"></i>guard <i class="r"></i>rejected <i class="p"></i>policy in force
      <i class="line"></i>violations, last 50
    </span>
  </div>
  <svg
    bind:this={box}
    viewBox="0 0 {W} {H}"
    preserveAspectRatio="none"
    role="slider"
    tabindex="0"
    aria-label="requests over time; arrow keys move through them"
    aria-valuemin={1}
    aria-valuemax={Math.max(n, 1)}
    aria-valuenow={app.pin ?? n}
    onmousemove={(e) => (hoverAt = at(e))}
    onmouseleave={() => (hoverAt = null)}
    onclick={(e) => { const i = at(e); if (i !== null) void app.pinRequest(i + 1); }}
    onkeydown={key}
  >
    <rect x="0" y={TOP} width={W} height={H - TOP} class="bg" />
    {#each marks as m (m.i)}
      {#if m.r}<rect x={x(m.i) - 0.6} y={H - 8} width="1.2" height="8" class="r" />{/if}
      {#if m.a}<rect x={x(m.i) - 0.8} y={TOP + 2} width="1.6" height={H - TOP - 4} class="a" />{/if}
      {#if m.g}<rect x={x(m.i) - 0.8} y={TOP + 2} width="1.6" height={H - TOP - 4} class="g" />{/if}
      {#if m.v}<rect x={x(m.i) - 0.9} y={TOP} width="1.8" height={H - TOP} class="v" />{/if}
    {/each}
    {#each arrivals as p (p.id)}
      <path d="M{x(p.at) - 4},0 L{x(p.at) + 4},0 L{x(p.at)},8 Z" class="p"><title>policy #{p.id} in force</title></path>
    {/each}
    {#if n > 1}<polyline points={rate} class="rate" />{/if}
    {#if app.pin !== null}<rect x={x(app.pin - 1) - 2} y={TOP - 2} width="4" height={H - TOP + 2} class="pin" />{/if}
    {#if hoverAt !== null}<rect x={x(hoverAt) - 0.6} y={TOP} width="1.2" height={H - TOP} class="hover" />{/if}
  </svg>
  {#if hoverAt !== null}
    {@const row = app.auditByN.get(hoverAt + 1)}
    <div class="tip">
      #{hoverAt + 1}{row ? ` · ${row.source} → ${row.destination}${row.respects === false ? " · breaks what was meant" : ""}${row.blocked ? " · rejected" : ""}` : ""}
    </div>
  {/if}
</div>

<style>
  .timeline { position: relative; padding: 4px 12px 10px; border-top: 1px solid var(--line); }
  .head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 3px; font-size: 11px; flex-wrap: wrap; }
  .keys { margin-left: auto; color: var(--dim); font-size: 10.5px; display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
  .keys i { display: inline-block; width: 7px; height: 9px; margin-left: 6px; border-radius: 1px; }
  .keys i.line { width: 14px; height: 2px; background: #ff9b9b; }
  i.v, rect.v { background: var(--red); fill: var(--red); }
  i.a, rect.a { background: var(--amber); fill: var(--amber); }
  i.g, rect.g { background: var(--violet); fill: var(--violet); }
  i.r, rect.r { background: #69738a; fill: #69738a; }
  i.p { background: var(--violet); clip-path: polygon(0 0, 100% 0, 50% 100%); }
  path.p { fill: var(--violet); }
  svg { width: 100%; height: 46px; display: block; cursor: pointer; }
  .bg { fill: var(--panel); }
  .rate { fill: none; stroke: #ff9b9b; stroke-width: 1.2; vector-effect: non-scaling-stroke; opacity: 0.8; }
  .pin { fill: #ffffff; }
  .hover { fill: var(--cyan); }
  .tip { position: absolute; right: 12px; top: 2px; font-size: 11px; color: var(--muted); background: var(--panel2); padding: 1px 8px; border-radius: 6px; }
</style>
