<script lang="ts">
  // One standing policy: it arrives (or is typed), is read back, conflicts are named, it is in force.
  // Hovering lights up on the map what it avoids and requires.
  import type { Group } from "../lib/feed";
  import { policyProblem } from "../lib/feed";
  import { scopeText } from "../lib/format";
  import { app } from "../lib/store.svelte";

  let { group }: { group: Group } = $props();
  const arrived = $derived(group.events.find((e) => e.kind === "policy_in"));
  const read = $derived(group.events.find((e) => e.kind === "policy_read"));
  const added = $derived(group.added);
  const id = $derived(group.policy);
  const text = $derived(arrived?.detail ?? (added?.data?.text as string | undefined) ?? (read?.data?.text as string | undefined) ?? "");
  const typed = $derived(added?.data?.source === "operator");
  const right = $derived(read?.data?.right as boolean | undefined);
  const scope = $derived(((added?.data?.line ?? read?.data?.line ?? "") as string).match(/scope=([^;]+)/)?.[1]);
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<article
  class="card"
  class:problem={policyProblem(group)}
  onmouseenter={() => id && (app.hover = id)}
  onmouseleave={() => (app.hover = null)}
>
  <div class="ch">
    <span class="id">{id ? `policy #${id}` : "policy"}</span>
    <span class="what">{typed ? "typed by you" : arrived ? "arrives" : "added"}</span>
    <span class="t">{group.events[0].hour.toFixed(1)} h</span>
  </div>
  {#if text}<div class="quote">{text}</div>{/if}
  <ul class="steps">
    {#if read}
      <li>
        <span class="ic">{#if right === false}<span class="bad">✗</span>{:else}<span class="good">✓</span>{/if}</span>
        <span>Read back: <b>{read.title.replace("reader: ", "")}</b>
          {#if right === false}<span class="bad"> (differs from the recorded meaning)</span>{:else if right}<span class="dim"> (matches the recorded meaning)</span>{/if}</span>
      </li>
    {:else if added}
      <li><span class="ic good">✓</span><span>Read back: <b>{added.detail}</b></span></li>
    {/if}
    {#each group.events.filter((e) => e.kind === "conflict") as e (e.n)}
      <li><span class="ic warn">⚠</span><span>{e.title}: {e.detail}</span></li>
    {/each}
    {#each group.events.filter((e) => e.kind === "not_applied" || e.kind === "unread") as e (e.n)}
      <li><span class="ic bad">!</span><span>{e.title}</span></li>
    {/each}
  </ul>
  {#if added}
    <div class="foot">
      <span class="badge pol">{added.title.replace(/^policy \d+ /, "")}</span>
      <span class="dim scope">{scopeText(scope)}</span>
    </div>
  {/if}
  {#if app.detail && (added?.data?.line || read?.data?.line)}
    <details>
      <summary>model lines</summary>
      <pre>line: {added?.data?.line ?? read?.data?.line}{#if read?.data?.truth}
recorded: {read.data.truth}{/if}</pre>
      {#if read?.data?.tapi}<pre>{JSON.stringify(read.data.tapi, null, 1)}</pre>{/if}
    </details>
  {/if}
</article>

<style>
  .card { margin: 6px 0; padding: 9px 11px; border: 1px solid var(--line); border-left: 3px solid var(--violet); border-radius: 8px; background: var(--panel); }
  .card:hover { border-color: #3d3470; background: #141128; }
  .problem { border-left-color: var(--red); background: #1a1013; }
  .ch { display: flex; gap: 8px; align-items: baseline; }
  .id { font-family: var(--mono); font-size: 11px; color: var(--violet); }
  .what { font-weight: 600; }
  .t { margin-left: auto; font-family: var(--mono); font-size: 10.5px; color: var(--dim); }
  .quote { margin: 4px 0 2px; }
  .steps { margin: 6px 0 0; padding: 0; list-style: none; }
  .steps li { display: flex; gap: 7px; padding: 2px 0; color: var(--muted); font-size: 12px; }
  .steps li b { color: var(--ink); font-weight: 500; }
  .ic { width: 14px; flex: none; text-align: center; }
  .foot { display: flex; align-items: center; gap: 8px; margin-top: 7px; padding-top: 6px; border-top: 1px solid var(--line); flex-wrap: wrap; }
  .scope { font-size: 11.5px; }
  details { margin-top: 6px; }
</style>
