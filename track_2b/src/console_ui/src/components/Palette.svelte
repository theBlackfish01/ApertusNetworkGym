<script lang="ts">
  // Ctrl+K: every action by name. "inspect 37" or "show 37" opens or shows request 37.
  import { onDestroy, onMount } from "svelte";
  import { app } from "../lib/store.svelte";

  type Command = { label: string; hint?: string; run: () => void | Promise<unknown> };
  let query = $state("");
  let index = $state(0);
  let input: HTMLInputElement | undefined = $state();
  let before: HTMLElement | null = null; // focus goes back there when the palette closes
  onMount(() => {
    before = document.activeElement as HTMLElement | null;
    input?.focus();
  });
  onDestroy(() => before?.focus?.());
  // the views and tabs live in Operate: a command about them switches there first
  const op = (fn: () => unknown) => () => {
    app.setMode("operate");
    return fn() as void;
  };

  const commands = $derived.by<Command[]>(() => {
    const s = app.state;
    const list: Command[] = [
      { label: app.playing ? "Pause the stream" : "Play the stream", hint: "space", run: () => app.toggle() },
      { label: "Decide the next request", hint: "s", run: () => app.step(1) },
      { label: "Decide the next ten requests", run: () => app.step(10) },
      { label: "Operate view", run: () => app.setMode("operate") },
      { label: "Race: four methods on the evaluation's stream", run: () => app.setMode("race") },
      { label: "Take the guided tour", run: () => (app.tourOpen = true) },
      { label: "Feed: everything", run: op(() => (app.filter = "all")) },
      { label: "Feed: requests", run: op(() => (app.filter = "requests")) },
      { label: "Feed: policies", run: op(() => (app.filter = "policies")) },
      { label: "Feed: problems only", run: op(() => (app.filter = "problems")) },
      { label: app.detail ? "Hide the model's lines" : "Show the model's lines", run: op(() => (app.detail = !app.detail)) },
      { label: "Open the audit trail", run: op(() => (app.tab = "audit")) },
      { label: "Open the policy report", run: op(() => (app.tab = "report")) },
      { label: "Open the policies over time", run: op(() => (app.tab = "timeline")) },
      { label: "Open the metrics", run: op(() => (app.tab = "metrics")) },
      { label: "Type a standing policy", run: () => focusCommand("policy") },
      { label: "Type an instruction for the next request", run: () => focusCommand("instruction") },
    ];
    if (app.lastDecision) list.push({ label: `Inspect the last decision (#${app.lastDecision.n})`, run: () => app.openInspector(app.lastDecision!.n) });
    if (s) {
      list.push({ label: `Inspect the next request's candidates (#${s.pending.n})`, run: () => app.openInspector(s.pending.n) });
      for (const p of s.policies.filter((p) => p.active)) list.push({ label: `Withdraw policy #${p.id}: ${p.readback}`, run: () => app.withdraw(p.id) });
      list.push({ label: s.settings.auto_answer ? "Answer questions myself" : "Let the simulated operator answer", run: () => app.settings({ auto_answer: !s.settings.auto_answer }) });
    }
    const number = query.match(/(\d+)/);
    if (number && s) {
      const n = Number(number[1]);
      if (n >= 1 && n <= s.stats.served + 1) {
        list.unshift({ label: `Inspect request #${n}`, run: () => app.openInspector(n) });
        if (n <= s.stats.served) list.unshift({ label: `Show request #${n} on the map`, run: () => app.pinRequest(n) });
      }
    }
    const words = query.toLowerCase().replace(/\d+/g, "").split(/\s+/).filter(Boolean);
    return list.filter((c) => words.every((w) => c.label.toLowerCase().includes(w)));
  });
  $effect(() => {
    if (index >= commands.length) index = Math.max(0, commands.length - 1);
  });

  function focusCommand(mode: "policy" | "instruction") {
    app.cmdMode = mode;
    app.setMode("operate");
    setTimeout(() => (document.querySelector<HTMLInputElement>('input[list="recordedList"]'))?.focus(), 30);
  }
  function close() {
    app.paletteOpen = false;
  }
  function run(command: Command | undefined) {
    if (!command) return;
    close();
    void command.run();
  }
  function key(event: KeyboardEvent) {
    if (event.key === "Escape") close();
    else if (event.key === "ArrowDown") index = Math.max(0, Math.min(index + 1, commands.length - 1));
    else if (event.key === "ArrowUp") index = Math.max(index - 1, 0);
    else if (event.key === "Enter") run(commands[index]);
    else if (event.key === "Tab") input?.focus(); // the input is the dialog's one stop: focus stays in it
    else return;
    event.preventDefault();
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="veil" onclick={close}>
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="palette" role="dialog" aria-modal="true" aria-label="commands" tabindex="-1" onclick={(e) => e.stopPropagation()}
       onkeydown={(e) => e.key === "Escape" && close()}>
    <input bind:this={input} type="search" bind:value={query} placeholder="a command, or a request number: inspect 37" onkeydown={key}
           aria-label="search the commands" role="combobox" aria-expanded="true" aria-controls="palette-list"
           aria-activedescendant={commands.length ? `palette-${index}` : undefined} />
    <ul role="listbox" id="palette-list" aria-label="commands">
      {#each commands as c, i (c.label)}
        <li id="palette-{i}" role="option" aria-selected={i === index} class:on={i === index} onmouseenter={() => (index = i)} onclick={() => run(c)}>
          <span>{c.label}</span>{#if c.hint}<kbd>{c.hint}</kbd>{/if}
        </li>
      {:else}
        <li class="dim">No command matches.</li>
      {/each}
    </ul>
  </div>
</div>

<style>
  .veil { position: fixed; inset: 0; background: #0009; z-index: 60; display: flex; justify-content: center; align-items: flex-start; padding-top: 12vh; }
  .palette { width: min(560px, 92vw); background: var(--panel2); border: 1px solid var(--line2); border-radius: 12px; box-shadow: 0 20px 50px #000c; overflow: hidden; }
  input { width: 100%; border: 0; border-bottom: 1px solid var(--line); border-radius: 0; padding: 12px 14px; font-size: 14px; background: transparent; }
  ul { list-style: none; margin: 0; padding: 6px; max-height: 50vh; overflow: auto; }
  li { display: flex; justify-content: space-between; gap: 10px; padding: 7px 10px; border-radius: 7px; cursor: pointer; font-size: 13px; }
  li.on { background: #1a3454; }
  kbd { font-family: var(--mono); font-size: 11px; color: var(--dim); border: 1px solid var(--line2); border-radius: 4px; padding: 0 5px; }
</style>
