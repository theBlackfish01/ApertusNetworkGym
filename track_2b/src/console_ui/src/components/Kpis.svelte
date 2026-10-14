<script lang="ts">
  import { pct } from "../lib/format";
  import { app } from "../lib/store.svelte";

  const s = $derived(app.state?.stats);
  type Tile = { label: string; value: string | number; title: string; alert?: boolean; problems?: boolean };
  const tiles = $derived<Tile[]>(
    s
      ? [
          { label: "served", value: s.served, title: "requests decided" },
          { label: "rejected", value: pct(s.rejected, s.served), title: "share of the decided requests that were rejected" },
          { label: "violations", value: s.violations, alert: s.violations > 0, problems: true,
            title: "decisions that break what was meant: the instruction and the policies in force, judged together" },
          { label: "policy breaches", value: s.policy_violations, alert: s.policy_violations > 0, problems: true,
            title: "routes that break a constraint a policy truly states" },
          { label: "questions", value: s.questions, problems: true, title: "times the operator was asked because the two readers differed" },
          { label: "to the decider", value: s.decider, title: "requests decided by the decider: instructions outside the language" },
          { label: "guard", value: s.guarded, problems: true, title: "decider routes replaced because they broke a constraint the line carries" },
          { label: "not applied", value: s.flagged + (s.unread || 0), title: "instructions or policies marked as not applicable, or not read" },
        ]
      : [],
  );
</script>

<div class="kpis">
  {#each tiles as t (t.label)}
    {#if t.problems}
      <button class="kpi" class:alert={t.alert} title="{t.title} — show the problems in the feed" onclick={() => (app.filter = "problems")}>
        <span class="v">{t.value}</span><span class="l">{t.label}</span>
      </button>
    {:else}
      <div class="kpi" title={t.title}><span class="v">{t.value}</span><span class="l">{t.label}</span></div>
    {/if}
  {/each}
</div>

<style>
  .kpis { display: grid; grid-template-columns: repeat(8, minmax(0, 1fr)); gap: 6px; padding: 10px 12px 4px; }
  @container stage (max-width: 820px) { .kpis { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
  .kpi { display: flex; flex-direction: column; align-items: flex-start; padding: 6px 8px; border: 1px solid var(--line); border-radius: 8px;
         background: var(--panel); text-align: left; min-width: 0; }
  button.kpi { cursor: pointer; font: inherit; }
  button.kpi:hover { border-color: var(--line2); }
  .v { font-size: 17px; font-weight: 650; font-variant-numeric: tabular-nums; line-height: 1.2; }
  .l { font-size: 10.5px; color: var(--dim); line-height: 1.2; }
  .alert { border-color: #4a2024; }
  .alert .v { color: var(--red); }
</style>
