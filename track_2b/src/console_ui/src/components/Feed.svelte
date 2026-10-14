<script lang="ts">
  import { buildGroups, filterGroups, type Filter } from "../lib/feed";
  import { app } from "../lib/store.svelte";
  import PolicyCard from "./PolicyCard.svelte";
  import RequestCard from "./RequestCard.svelte";

  const FILTERS: [Filter, string][] = [["all", "All"], ["requests", "Requests"], ["policies", "Policies"], ["problems", "Problems"]];
  const groups = $derived(app.state ? filterGroups(buildGroups(app.state.feed, app.detail), app.filter, app.auditByN).slice(0, 80) : []);
</script>

<section class="feed" aria-label="what the system is doing" data-tour="feed">
  <div class="head">
    <h2>What the system is doing · newest first</h2>
    <div class="filters" role="tablist" aria-label="filter the feed">
      {#each FILTERS as [key, label] (key)}
        <button role="tab" aria-selected={app.filter === key} class:on={app.filter === key} onclick={() => (app.filter = key)}>{label}</button>
      {/each}
    </div>
  </div>
  <div class="events scroll">
    {#each groups as g (g.type + ":" + (g.n ?? g.events[0].n))}
      {#if g.type === "request"}
        <RequestCard group={g} />
      {:else if g.type === "policy"}
        <PolicyCard group={g} />
      {:else}
        {@const e = g.events[0]}
        <div class="note"><span class="mono dim">{e.hour.toFixed(1)} h</span> {e.title}{#if e.detail}<span class="dim"> · {e.detail}</span>{/if}</div>
      {/if}
    {:else}
      <div class="empty">{app.filter === "problems" ? "No problems so far." : "Nothing yet. Press Play or Step, or take the Tour."}</div>
    {/each}
  </div>
</section>

<style>
  .feed { display: flex; flex-direction: column; min-height: 0; border-right: 1px solid var(--line); }
  .head { display: flex; flex-direction: column; gap: 6px; padding: 11px 14px 7px; }
  .filters { display: flex; gap: 4px; }
  .filters button { padding: 2px 9px; font-size: 11px; border-radius: 999px; background: transparent; color: var(--muted); }
  .filters button.on { color: var(--ink); border-color: var(--cyan); background: #10263a; }
  .events { flex: 1; overflow: auto; padding: 0 10px 12px; min-height: 0; }
  .note { margin: 4px 0; padding: 4px 10px; border-left: 3px solid var(--line); color: var(--muted); font-size: 12px; }
  .empty { color: var(--dim); padding: 18px; text-align: center; }
</style>
