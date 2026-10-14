<script lang="ts">
  // The network: links shaded by occupation, what the policies avoid (red) and require (green), a
  // route (cyan when just set up, white when a past request is shown), the end points of the next
  // request (amber), and a highlighted policy. Wheel zooms, drag pans, double-click resets; the
  // compact form (race lanes) draws no labels except the end points and does not zoom.
  import { linkKey, project, routeLinks } from "../lib/geo";
  import type { LinkRow, NodeRow } from "../lib/types";

  interface Props {
    nodes: NodeRow[];
    links: LinkRow[];
    avoidLinks?: Set<string>;
    avoidNodes?: Set<string>;
    via?: Set<string>;
    route?: string[] | null;
    routeTone?: "live" | "past" | "bad";
    pending?: string[];
    hotLinks?: Set<string>;
    hotNodes?: Set<string>;
    hotVia?: Set<string>;
    animate?: boolean;
    compact?: boolean;
    label?: string;
  }
  let {
    nodes, links, avoidLinks = new Set(), avoidNodes = new Set(), via = new Set(), route = null, routeTone = "live",
    pending = [], hotLinks = new Set(), hotNodes = new Set(), hotVia = new Set(), animate = false, compact = false,
    label = "network map",
  }: Props = $props();

  const W = 800, H = 560;
  const P = $derived(project(nodes, W, H, compact ? 18 : 34));
  const onRoute = $derived(routeLinks(route));
  const ends = $derived(new Set(route && route.length ? [route[0], route[route.length - 1]] : []));
  const pend = $derived(new Set(pending));
  const routeKey = $derived((route ?? []).join(">"));

  let view = $state({ x: 0, y: 0, w: W, h: H });
  let svg: SVGSVGElement | undefined = $state();
  let drag: { x: number; y: number; vx: number; vy: number } | null = null;

  function shade(used: number): string {
    const light = Math.round(55 + 160 * used);
    return `rgb(${Math.round(light * 0.5)},${Math.round(light * 0.72)},${light})`;
  }
  function toView(event: MouseEvent): { x: number; y: number } {
    const box = svg!.getBoundingClientRect();
    const scale = Math.max(view.w / box.width, view.h / box.height);
    const ox = (box.width * scale - view.w) / 2, oy = (box.height * scale - view.h) / 2;
    return { x: view.x - ox + (event.clientX - box.left) * scale, y: view.y - oy + (event.clientY - box.top) * scale };
  }
  function wheel(event: WheelEvent) {
    if (compact) return;
    event.preventDefault();
    const at = toView(event);
    const factor = Math.exp(event.deltaY * 0.0015);
    const w = Math.min(W * 1.2, Math.max(W / 6, view.w * factor)), h = (w * H) / W;
    view = { x: at.x - ((at.x - view.x) * w) / view.w, y: at.y - ((at.y - view.y) * h) / view.h, w, h };
  }
  function down(event: PointerEvent) {
    if (compact || event.button !== 0) return;
    drag = { x: event.clientX, y: event.clientY, vx: view.x, vy: view.y };
    (event.currentTarget as Element).setPointerCapture(event.pointerId);
  }
  function move(event: PointerEvent) {
    if (!drag || !svg) return;
    const box = svg.getBoundingClientRect();
    const scale = Math.max(view.w / box.width, view.h / box.height);
    view = { ...view, x: drag.vx - (event.clientX - drag.x) * scale, y: drag.vy - (event.clientY - drag.y) * scale };
  }
  function up() {
    drag = null;
  }
  function reset() {
    view = { x: 0, y: 0, w: W, h: H };
  }
  const zoomed = $derived(view.w < W - 1 || view.x !== 0 || view.y !== 0);
</script>

<div class="map" class:compact>
  <svg
    bind:this={svg}
    viewBox="{view.x} {view.y} {view.w} {view.h}"
    preserveAspectRatio="xMidYMid meet"
    role="img"
    aria-label={label}
    onwheel={wheel}
    onpointerdown={down}
    onpointermove={move}
    onpointerup={up}
    onpointercancel={up}
    ondblclick={reset}
  >
    {#each links as l (l.a + "|" + l.b)}
      {@const k = linkKey(l.a, l.b)}
      {@const a = P[l.a]}
      {@const b = P[l.b]}
      {#if a && b}
        <line
          class="link"
          class:avoid={avoidLinks.has(k)}
          class:hot={hotLinks.has(k)}
          class:dimmed={compact && onRoute.size > 0 && !onRoute.has(k)}
          x1={a.x}
          y1={a.y}
          x2={b.x}
          y2={b.y}
          style:stroke={avoidLinks.has(k) || hotLinks.has(k) ? null : shade(l.used)}
          style:stroke-width={avoidLinks.has(k) || hotLinks.has(k) ? null : `${(compact ? 1.2 : 1.4) + 3.2 * l.used}px`}
        ><title>{l.a} – {l.b}{l.km ? `: ${l.km} km` : ""}, {Math.round(100 * l.used)} % of slots in use</title></line>
      {/if}
    {/each}
    {#if route && route.length > 1}
      {#key routeKey}
        <polyline
          class="route {routeTone}"
          class:flow={animate && routeTone === "live"}
          fill="none"
          points={route.map((n) => `${P[n]?.x},${P[n]?.y}`).join(" ")}
        />
      {/key}
    {/if}
    {#each nodes as n (n.name)}
      {@const p = P[n.name]}
      {@const strong = ends.has(n.name) || pend.has(n.name) || hotNodes.has(n.name)}
      <circle
        class="node"
        class:end={ends.has(n.name)}
        class:pend={!ends.has(n.name) && pend.has(n.name)}
        class:via={via.has(n.name) || hotVia.has(n.name)}
        class:avoid={(avoidNodes.has(n.name) || hotNodes.has(n.name)) && !hotVia.has(n.name)}
        class:hot={hotNodes.has(n.name) || hotVia.has(n.name)}
        cx={p.x}
        cy={p.y}
        r={compact ? (strong ? 6 : 3.4) : strong ? 5.6 : 4.4}
      ><title>{n.name}</title></circle>
      {#if !compact || ends.has(n.name) || pend.has(n.name)}
        <text class="label" class:key={strong} class:big={compact} x={p.x + 7} y={p.y - 6}>{n.name}</text>
      {/if}
    {/each}
  </svg>
  {#if zoomed && !compact}
    <button class="reset ghost" onclick={reset} title="show the whole network (double-click the map)">reset view</button>
  {/if}
</div>

<style>
  .map { position: relative; width: 100%; height: 100%; }
  svg { position: absolute; inset: 0; width: 100%; height: 100%; display: block; cursor: grab; touch-action: none; }
  .compact svg { cursor: default; }
  svg:active { cursor: grabbing; }
  .link { stroke: #2b3a57; stroke-width: 1.6; transition: stroke 0.25s; }
  .link.avoid { stroke: var(--red); stroke-dasharray: 5 4; stroke-width: 2.4; }
  .link.hot { stroke: var(--red); stroke-width: 5; filter: drop-shadow(0 0 4px #ff6262); }
  .link.dimmed { opacity: 0.45; }
  .route { stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; }
  .route.live { stroke: var(--cyan); }
  .route.past { stroke: #ffffff; stroke-width: 3.4; opacity: 0.92; }
  .route.bad { stroke: var(--red); }
  .route.flow { stroke-dasharray: 8 6; animation: flow 1.4s linear 2; }
  @keyframes flow { to { stroke-dashoffset: -28; } }
  .node { fill: var(--bg); stroke: #6a7a9a; stroke-width: 1.4; }
  .node.via { stroke: var(--green); stroke-width: 3; }
  .node.avoid { stroke: var(--red); stroke-width: 3; }
  .node.end { fill: var(--cyan); stroke: var(--cyan); }
  .node.pend { stroke: var(--amber); stroke-width: 3; }
  .node.hot { stroke-width: 4.5; filter: drop-shadow(0 0 4px currentColor); }
  .label { font-size: 10.5px; fill: #9aa6bd; pointer-events: none; paint-order: stroke; stroke: var(--bg); stroke-width: 3px; stroke-linejoin: round; }
  .label.key { fill: var(--ink); font-weight: 600; }
  .label.big { font-size: 22px; stroke-width: 5px; }
  .reset { position: absolute; right: 10px; bottom: 10px; padding: 2px 9px; font-size: 11px; background: var(--panel2); }
</style>
