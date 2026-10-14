<script lang="ts">
  import { app } from "../lib/store.svelte";

  let menu: HTMLDetailsElement | undefined = $state();
  const shortcut = /Mac|iPhone|iPad/.test(navigator.userAgent) ? "⌘K" : "Ctrl K";
  const s = $derived(app.state);
  const modeTitle = $derived(
    s
      ? `readers of per-request instructions: ${s.mode.hybrid}\nreader of standing policies: ${s.mode.reader}\ndecider: ${s.mode.decider}` +
          (s.mode.live ? `\nmodel server: ${s.mode.base_url}` : "\nno model server: every reading comes from the stored answers")
      : "",
  );
  function outside(event: MouseEvent) {
    if (menu?.open && !menu.contains(event.target as Node)) menu.open = false;
  }
</script>

<svelte:window onclick={outside} />

<header data-tour="header">
  <h1>Lightpath console</h1>
  {#if s}
    <span class="net">{s.topology} · {s.stats.load} Erlang · seed {s.stats.seed}</span>
    <span class="pill" class:live={s.mode.live} title={modeTitle}>
      <span class="dot"></span>{s.mode.live ? "Live: models on this machine" : "Recorded answers"}
    </span>
    {#if app.mode === "operate"}<span class="clock" title="the simulator's clock">hour {s.now.toFixed(2)}</span>{/if}
  {:else}
    <span class="net">connecting…</span>
  {/if}

  <nav class="modes" aria-label="view">
    <button class:on={app.mode === "operate"} onclick={() => app.setMode("operate")} title="the operator's view of one stream">Operate</button>
    <button class:on={app.mode === "race"} onclick={() => app.setMode("race")} title="four methods on the evaluation's stream, side by side">Race</button>
  </nav>

  <span class="spacer"></span>

  {#if app.mode === "operate"}
    <div class="transport">
      <button class="play" class:on={app.playing} onclick={() => app.toggle()} title="play or pause the stream (space)" disabled={!s}>
        {app.playing ? "❚❚ Pause" : "▶ Play"}
      </button>
      <select bind:value={app.pace} title="requests per second" aria-label="pace">
        <option value={1000}>1 /s</option>
        <option value={500}>2 /s</option>
        <option value={200}>5 /s</option>
        <option value={50}>fast</option>
      </select>
      <button class="ghost" onclick={() => app.step(1)} title="decide the next request (s)" disabled={!s || app.playing}>Step</button>
      <button class="ghost" onclick={() => app.step(10)} title="decide the next ten requests" disabled={!s || app.playing}>+10</button>
    </div>
    <details class="menu" bind:this={menu}>
      <summary>Stream ▾</summary>
      {#if s}
        <div class="panel">
          <label><input type="checkbox" checked={s.settings.arrivals} onchange={(e) => app.settings({ arrivals: e.currentTarget.checked })} />
            <span>Policies arrive<small>standing policies arrive on the schedule of the evaluation's policy stream</small></span></label>
          <label><input type="checkbox" checked={s.settings.mix} onchange={(e) => app.settings({ mix: e.currentTarget.checked })} />
            <span>Instructions with requests<small>each request carries an instruction drawn from the mixed stream</small></span></label>
          <label><input type="checkbox" checked={s.settings.auto_answer} onchange={(e) => app.settings({ auto_answer: e.currentTarget.checked })} />
            <span>Simulated operator<small>questions are answered with the recorded meaning, as in the closed-loop evaluation</small></span></label>
          <hr />
          <label><input type="checkbox" bind:checked={app.detail} />
            <span>Show the model's lines<small>the lines of the policy language, recorded meanings, TAPI constraints and internal steps</small></span></label>
        </div>
      {/if}
    </details>
  {/if}
  <button class="ghost" onclick={() => (app.tourOpen = true)} title="a guided tour of what the system does">Tour</button>
  <button class="ghost kbd" onclick={() => (app.paletteOpen = true)} title="every command by name">{shortcut}</button>
</header>

<style>
  header { display: flex; align-items: center; gap: 12px; padding: 8px 16px; border-bottom: 1px solid var(--line); background: var(--panel); flex-wrap: wrap; }
  h1 { font-size: 15px; margin: 0; font-weight: 650; letter-spacing: 0.01em; white-space: nowrap; }
  .net { color: var(--muted); font-size: 12px; white-space: nowrap; }
  .pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border: 1px solid var(--line2); border-radius: 999px; font-size: 11.5px;
          color: var(--muted); background: var(--panel2); white-space: nowrap; cursor: default; }
  .pill .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--amber); }
  .pill.live { color: var(--green); border-color: #1f4a3a; }
  .pill.live .dot { background: var(--green); box-shadow: 0 0 6px var(--green); }
  .clock { font-family: var(--mono); font-size: 12px; }
  .modes { display: inline-flex; border: 1px solid var(--line2); border-radius: 8px; overflow: hidden; margin-left: 6px; }
  .modes button { border: 0; border-radius: 0; background: transparent; color: var(--muted); padding: 5px 12px; }
  .modes button.on { background: #1a3454; color: var(--ink); }
  .spacer { flex: 1; }
  .transport { display: flex; align-items: center; gap: 6px; }
  .play { min-width: 84px; }
  .play.on { border-color: var(--cyan); color: var(--cyan); }
  .menu { position: relative; }
  .menu > summary { list-style: none; cursor: pointer; padding: 5px 11px; border: 1px solid var(--line2); border-radius: 7px; background: var(--panel2);
                    font-size: 12.5px; color: var(--ink); }
  .menu > summary::-webkit-details-marker { display: none; }
  .menu[open] > summary { border-color: var(--cyan); }
  .panel { position: absolute; right: 0; top: calc(100% + 6px); z-index: 40; width: 300px; padding: 10px 12px; background: var(--panel2);
           border: 1px solid var(--line2); border-radius: 10px; box-shadow: 0 10px 30px #0008; }
  label { display: flex; gap: 9px; align-items: flex-start; padding: 6px 0; cursor: pointer; font-size: 12.5px; }
  label input { accent-color: var(--cyan); margin-top: 3px; }
  label small { display: block; color: var(--dim); font-size: 11px; line-height: 1.35; }
  hr { border: 0; border-top: 1px solid var(--line); margin: 6px 0; }
  .kbd { font-family: var(--mono); font-size: 11.5px; }
</style>
