<script lang="ts">
  // The race: the evaluation's own stream (the mixed condition), decided by four methods side by
  // side from the answers stored when the closed loop was run. The paper's comparison, live.
  import { pct } from "../lib/format";
  import { app } from "../lib/store.svelte";
  import RaceChart from "./RaceChart.svelte";
  import RaceLane from "./RaceLane.svelte";

  const COLORS: Record<string, string> = {
    first_fit: "var(--m-firstfit)", decider: "var(--m-decider)", reader: "var(--m-reader)", hybrid: "var(--m-hybrid)",
  };
  const r = $derived(app.race);
  // the race of the operate stream's load and seed by default, set once: the operator's choice then stays
  let load = $state(app.race.load ?? app.state?.race_default.load ?? 390);
  let seed = $state(app.race.seed ?? app.state?.race_default.seed ?? 1);
  const nodes = $derived(app.state?.nodes ?? []);
  const last = $derived(r.last ?? null);
  const done = $derived(r.status === "ready" && (r.requests ?? 0) >= (r.window ?? 2000));
  const CLASSES = ["inside the language", "carried in part", "types never shown", "nothing to apply"];
</script>

{#snippet method(key: string, name: string)}<b class="method"><i style:background={COLORS[key]}></i>{name}</b>{/snippet}

<div class="race">
  <div class="controls">
    <h2>Race · four methods, one stream</h2>
    <label>load <select bind:value={load} disabled={app.racePlaying}><option value={240}>240 Erlang</option><option value={390}>390 Erlang</option></select></label>
    <label>seed <select bind:value={seed} disabled={app.racePlaying}><option value={1}>1</option><option value={2}>2</option><option value={3}>3</option></select></label>
    <button class="primary" onclick={() => app.raceStart(load, seed)} disabled={r.status === "preparing"}>
      {r.status === "off" ? "Prepare the race" : "Start again"}
    </button>
    {#if r.status === "ready"}
      <button class:on={app.racePlaying} onclick={() => (app.racePlaying ? app.racePause() : app.racePlay())} disabled={done}>
        {app.racePlaying ? "❚❚ Pause" : "▶ Run"}
      </button>
      <button class="ghost" onclick={() => app.raceStep(1)} disabled={app.racePlaying || done}>Step</button>
      <button class="ghost" onclick={() => app.raceStep(50)} disabled={app.racePlaying || done}>+50</button>
      <label>speed <select bind:value={app.raceSpeed}><option value={1}>7 /s</option><option value={2}>14 /s</option><option value={5}>35 /s</option><option value={15}>fast</option></select></label>
      <span class="count"><b>{r.requests}</b> of {r.window} requests{#if done} · complete{/if}</span>
    {/if}
  </div>

  {#if r.status === "off" || r.status === "preparing"}
    <div class="intro">
      <p>The race decides the evaluation's own stream, the mixed condition of the paper (load {load} Erlang, seed {seed}), four times over: by
        {@render method("first_fit", "first fit")}, which ignores the instruction; by the {@render method("decider", "decider")}, which reads it with every
        request; by the {@render method("reader", "reader with the rule engine")}; and by the {@render method("hybrid", "hybrid")}. Every decision is
        replayed from the answers stored when the closed loop was run, so no model is needed, and each lane is checked against its stored run at the end.</p>
      {#if r.status === "preparing"}
        <div>Preparing the four networks… {Math.round(100 * (r.progress ?? 0))}%</div>
        <div class="progress"><i style:width="{Math.round(100 * (r.progress ?? 0))}%"></i></div>
      {:else}
        <p class="dim">Preparing takes about half a minute: each lane warms its network up for 1,000 requests, as the evaluation did.</p>
      {/if}
    </div>
  {:else if r.status === "error"}
    <div class="intro bad">{(r.requests ?? 0) > 0 ? `The race stopped at request ${r.requests}` : "The race could not be prepared"}: {r.error}</div>
  {:else if r.lanes}
    <div class="request">
      {#if last}
        <span class="id">#{last.n}</span>
        <b>{last.source} → {last.destination}, {last.bit_rate} Gb/s</b>
        {#if last.text !== "none"}<span class="quote">{last.text}</span>{:else}<span class="dim">no instruction</span>{/if}
        <span class="tag">{last.class}</span>
      {:else}
        <span class="dim">Press Run or Step: each request is decided by all four at once.</span>
      {/if}
    </div>
    <div class="lanes">
      {#each r.lanes as lane (lane.key)}
        <RaceLane {lane} {nodes} request={last} color={COLORS[lane.key]} />
      {/each}
    </div>
    <div class="bottom">
      <div class="chart">
        <h2>Violations so far</h2>
        <RaceChart lanes={r.lanes} every={r.every ?? 10} colors={COLORS} window={r.window ?? 2000} />
      </div>
      <div class="classes">
        <h2>By class of instruction</h2>
        <table>
          <thead><tr><th></th>{#each r.lanes as lane (lane.key)}<th class="num"><i class="dot" style:background={COLORS[lane.key]}></i>{lane.label}</th>{/each}</tr></thead>
          <tbody>
            {#each CLASSES as c (c)}
              <tr><td>{c}</td>{#each r.lanes as lane (lane.key)}<td class="num">{pct(lane.classes[c]?.violations ?? 0, lane.classes[c]?.n ?? 0)}</td>{/each}</tr>
            {/each}
            <tr class="all"><td>all requests</td>{#each r.lanes as lane (lane.key)}<td class="num">{pct(lane.violations, lane.served)}</td>{/each}</tr>
          </tbody>
        </table>
        <p class="dim small">Violations as a share of each class's requests. The stream: 45% inside the language, 10% carried in part, 15% of types never
          shown, 30% with nothing to apply.</p>
      </div>
    </div>
  {/if}
</div>

<style>
  .race { display: flex; flex-direction: column; min-height: 0; height: 100%; padding: 10px 14px 12px; gap: 10px; overflow: auto; }
  .controls { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .controls h2 { margin-right: 6px; }
  label { font-size: 12px; color: var(--muted); display: inline-flex; align-items: center; gap: 5px; }
  button.on { border-color: var(--cyan); color: var(--cyan); }
  .count { margin-left: auto; color: var(--muted); font-size: 12px; }
  .count b { color: var(--ink); font-variant-numeric: tabular-nums; }
  .intro { max-width: 760px; margin: 40px auto; font-size: 14px; line-height: 1.6; }
  .method { white-space: nowrap; }
  .method i, th i.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; vertical-align: 1px; }
  .progress { height: 6px; background: var(--line); border-radius: 3px; margin-top: 10px; overflow: hidden; }
  .progress i { display: block; height: 100%; background: var(--cyan); transition: width 0.4s; }
  .request { display: flex; align-items: baseline; gap: 10px; padding: 8px 12px; border: 1px solid var(--line); border-radius: 9px; background: var(--panel);
             flex-wrap: wrap; min-height: 38px; }
  .id { font-family: var(--mono); color: var(--dim); }
  .lanes { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; flex: 1; min-height: 320px; }
  @media (max-width: 1250px) { .lanes { grid-template-columns: repeat(2, minmax(0, 1fr)); } .lanes :global(.lane) { min-height: 300px; } }
  .bottom { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 12px; min-height: 210px; }
  @media (max-width: 1000px) { .bottom { grid-template-columns: 1fr; } }
  @media (max-width: 640px) {
    .race { padding: 8px 10px 12px; }
    .lanes { grid-template-columns: minmax(0, 1fr); }
    .count { margin-left: 0; flex-basis: 100%; }
    .intro { margin: 16px auto; }
  }
  .chart, .classes { padding: 9px 12px; border: 1px solid var(--line); border-radius: 9px; background: var(--panel); display: flex; flex-direction: column; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 6px; }
  th, td { padding: 4px 6px; border-bottom: 1px solid var(--line); text-align: left; }
  th { font-size: 11px; }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  tr.all td { font-weight: 600; }
  .small { font-size: 11px; margin: 6px 0 0; }
</style>
