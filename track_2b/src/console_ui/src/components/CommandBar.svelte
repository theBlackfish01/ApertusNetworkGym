<script lang="ts">
  // One command line for both kinds of operator text, and what the reader made of it in a panel
  // above: read back, conflicts, a preview on a copy of the network, the TAPI constraint.
  import { routeText, scopeText } from "../lib/format";
  import { app } from "../lib/store.svelte";
  import type { Reading } from "../lib/types";

  let text = $state("");
  let ownLine = $state("");
  let input: HTMLInputElement | undefined = $state();
  const listed = $derived((app.cmdMode === "policy" ? app.recorded.policies : app.recorded.instructions).slice(0, 600));
  const live = $derived(app.state?.mode.live ?? false);
  $effect(() => {
    const sheet = app.sheet;
    if (sheet?.kind === "policy") ownLine = sheet.read.line;
    else if (sheet?.kind === "instruction") ownLine = sheet.read.readings[0]?.line ?? "";
  });

  function consequence(r: Reading): string {
    const d = r.decision;
    if (d.to_decider) return "would hand the next request to the decider";
    if (d.reject || !d.route) return "would reject the next request";
    return `would route the next request ${routeText(d.route)}`;
  }
  async function add(line?: string) {
    if (await app.addPolicy(line)) text = "";
  }
  export function focus(mode?: "policy" | "instruction") {
    if (mode) app.cmdMode = mode;
    input?.focus();
  }
</script>

<div class="bar">
  {#if app.sheet}
    <div class="sheet scroll" role="dialog" aria-label="what was read">
      <button class="ghost close" onclick={() => (app.sheet = null)} title="close (Esc)" aria-label="close">×</button>
      {#if app.sheet.kind === "policy"}
        {@const r = app.sheet.read}
        <h2>Standing policy, as read</h2>
        <div class="quote said">{r.text}</div>
        <div class="reading">
          <div class="rb"><b>{r.readback}</b></div>
          <div class="dim small">{scopeText(r.scope)} · {r.until === null ? "until withdrawn" : `${r.until} h`} · {r.status} · {live ? `read in ${r.seconds} s` : "stored answer"}</div>
          {#each r.conflicts as c, i (i)}
            <div class="conf {c.kind}"><b>{c.kind}</b>: {c.why}{#if c.with_text} (policy #{c.with}: “{c.with_text}”){/if}</div>
          {/each}
          {#if r.preview}
            <div class="preview">Preview of the next {r.preview.horizon} requests on a copy of the network: it covers <b>{r.preview.covers}</b> of them;
              <b>{r.preview.with.changed}</b> decisions differ (its own, and knock-on effects on later requests); rejections
              {r.preview.without.blocked} → <b>{r.preview.with.blocked}</b>.</div>
          {/if}
          <div class="row">
            <button class="primary" disabled={!r.applies} onclick={() => add()}>
              {r.conflicts.some((c) => c.kind === "contradiction") ? "Add despite the contradiction" : "Add policy"}
            </button>
            <button class="ghost" onclick={() => (app.sheet = null)}>Discard</button>
          </div>
          <details>
            <summary>the line and the TAPI constraint, or write the line yourself</summary>
            <div class="row"><input type="text" bind:value={ownLine} aria-label="your line" /><button onclick={() => add(ownLine)}>Add my line</button></div>
            <pre>{JSON.stringify(r.tapi, null, 1)}</pre>
          </details>
        </div>
      {:else if app.sheet.kind === "instruction"}
        {@const r = app.sheet.read}
        <h2>Instruction for request #{r.request?.n}, as read</h2>
        <div class="quote said">{r.text}</div>
        {#if r.differ}
          <div class="reading"><b class="warn">The two readers disagree</b> · {r.decide_differently
            ? "and would decide this request differently: you are asked when it is decided, unless you settle it now."
            : "but decide this request alike; the first reading stands until a request tells them apart."}</div>
        {:else}
          <div class="reading"><b class="good">Both readers agree.</b> It applies to the next request.</div>
        {/if}
        {#each r.readings as rd, i (rd.reader)}
          {#if r.differ || i === 0}
            <div class="reading">
              <div><b>{r.differ ? rd.reader : "Reading"}</b> <span class="dim">{rd.status}</span></div>
              <div class="rb">{rd.readback}</div>
              <div class="dim small">{consequence(rd)}</div>
              {#if r.differ}<div class="row"><button class="primary" onclick={() => app.confirmInstruction(rd.line)}>Use this reading</button></div>{/if}
              <details><summary>the line and the TAPI constraint</summary><pre>{rd.line}</pre><pre>{JSON.stringify(rd.tapi, null, 1)}</pre></details>
            </div>
          {/if}
        {/each}
        <details>
          <summary>write the line yourself</summary>
          <div class="row"><input type="text" bind:value={ownLine} aria-label="your line" /><button onclick={() => app.confirmInstruction(ownLine)}>Use my line</button></div>
        </details>
      {:else}
        <div class="good">Settled: <span class="mono">{app.sheet.line}</span>. It applies to the next request.</div>
      {/if}
    </div>
  {/if}

  <div class="cmd">
    <div class="seg" role="radiogroup" aria-label="what you are typing">
      <button role="radio" aria-checked={app.cmdMode === "policy"} class:on={app.cmdMode === "policy"} onclick={() => (app.cmdMode = "policy")}>Standing policy</button>
      <button role="radio" aria-checked={app.cmdMode === "instruction"} class:on={app.cmdMode === "instruction"} onclick={() => (app.cmdMode = "instruction")}><span class="long">Instruction for the next request</span><span class="short">Next request</span></button>
    </div>
    <input
      bind:this={input}
      type="text"
      bind:value={text}
      list="recordedList"
      aria-label={app.cmdMode === "policy" ? "a standing policy" : "an instruction for the next request"}
      placeholder={app.cmdMode === "policy"
        ? `type a standing policy in any language${live ? "" : ", or pick one that was read before"}`
        : `type an instruction for the next request${live ? "" : ", or pick one that was read before"}`}
      onkeydown={(e) => e.key === "Enter" && !e.isComposing && !app.reading && app.read(text)}
    />
    <datalist id="recordedList">
      {#each listed as r (r.text)}<option value={r.text}>{r.lang} · {r.set}</option>{/each}
    </datalist>
    <button class="primary" disabled={app.reading || !text.trim()} onclick={() => app.read(text)}>{app.reading ? "Reading…" : "Read"}</button>
    <button class="ghost" onclick={() => { text = ""; void app.clearInstruction(); }}>Clear</button>
  </div>
  {#if app.error}<div class="err" role="alert">{app.error} <button class="ghost" onclick={() => (app.error = "")} aria-label="dismiss">×</button></div>{/if}
</div>

<style>
  .bar { position: relative; }
  .cmd { display: flex; gap: 8px; padding: 9px 16px; align-items: center; }
  .seg { display: inline-flex; border: 1px solid var(--line2); border-radius: 8px; overflow: hidden; flex: none; }
  .seg button { border: 0; border-radius: 0; background: transparent; color: var(--muted); padding: 6px 11px; }
  .seg button.on { background: #1a3454; color: var(--ink); }
  .short { display: none; }
  input[type="text"] { flex: 1; min-width: 160px; }
  .sheet { position: absolute; left: 16px; bottom: calc(100% + 8px); width: min(760px, calc(100% - 32px)); max-height: 60vh; overflow: auto; z-index: 30;
           padding: 12px 14px 14px; background: var(--panel2); border: 1px solid var(--line2); border-radius: 10px; box-shadow: 0 12px 34px #000a; }
  .close { float: right; padding: 0 8px; }
  .said { margin: 8px 0 4px; }
  .reading { padding: 8px 9px; border: 1px solid var(--line2); border-radius: 7px; margin-top: 7px; background: var(--panel3); }
  .rb { margin: 2px 0 4px; }
  .small { font-size: 12px; }
  .row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-top: 8px; }
  .row input { flex: 1; min-width: 240px; }
  .conf { padding: 5px 8px; border-radius: 6px; margin-top: 6px; font-size: 12px; }
  .conf.contradiction { background: #2a1414; color: #ff9a9a; }
  .conf.override { background: #2a2210; color: #ffd58a; }
  .preview { margin-top: 7px; font-size: 12.5px; }
  details { margin-top: 8px; }
  .err { color: var(--red); padding: 0 16px 6px; display: flex; align-items: center; gap: 6px; }
  .err button { padding: 0 6px; }
  @media (max-width: 760px) {
    .cmd { flex-wrap: wrap; padding: 8px 12px; }
    .seg { flex: 1 1 100%; }
    .seg button { flex: 1; padding: 6px 8px; }
    .long { display: none; }
    .short { display: inline; }
    input[type="text"] { min-width: 0; }
    .sheet { left: 8px; width: calc(100% - 16px); }
    .row input { min-width: 0; }
  }
</style>
