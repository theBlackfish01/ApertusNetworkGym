<script lang="ts">
  import { onMount } from "svelte";
  import CommandBar from "./components/CommandBar.svelte";
  import Drawer from "./components/Drawer.svelte";
  import Feed from "./components/Feed.svelte";
  import Header from "./components/Header.svelte";
  import Inspector from "./components/Inspector.svelte";
  import Kpis from "./components/Kpis.svelte";
  import OperateMap from "./components/OperateMap.svelte";
  import Palette from "./components/Palette.svelte";
  import RaceView from "./components/RaceView.svelte";
  import Rail from "./components/Rail.svelte";
  import Timeline from "./components/Timeline.svelte";
  import Tour from "./components/Tour.svelte";
  import { app } from "./lib/store.svelte";

  onMount(() => {
    void app.boot();
  });

  function typing(): boolean {
    const el = document.activeElement as HTMLElement | null;
    return !!el && (["INPUT", "SELECT", "TEXTAREA"].includes(el.tagName) || el.isContentEditable);
  }
  // Space on a focused button, link, summary or widget belongs to it (a keyboard user presses it to
  // activate "Withdraw" or "Stream"), not to the stream.
  function onControl(): boolean {
    const el = document.activeElement as HTMLElement | null;
    return !!el && el !== document.body && (["BUTTON", "A", "SUMMARY"].includes(el.tagName) || el.hasAttribute("role") || el.tabIndex >= 0);
  }
  function key(event: KeyboardEvent) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      app.paletteOpen = !app.paletteOpen;
      return;
    }
    if (event.defaultPrevented) return; // a dialog (the palette, the tour) has handled this key already
    if (typing() || app.paletteOpen || app.tourOpen) return;
    if (event.key === "Escape") {
      if (app.sheet) app.sheet = null;
      else if (app.inspect !== null) app.inspect = null;
      else app.unpin();
    } else if (event.code === "Space" && onControl()) {
      return;
    } else if (app.mode === "operate" && event.code === "Space") {
      event.preventDefault();
      app.toggle();
    } else if (app.mode === "operate" && event.key === "s" && !app.playing) {
      void app.step(1);
    } else if (app.mode === "race" && event.code === "Space") {
      event.preventDefault();
      if (app.racePlaying) app.racePause();
      else void app.racePlay();
    }
  }
</script>

<svelte:window onkeydown={key} />

<div class="shell">
  <Header />
  {#if !app.state}
    <div class="boot">
      <div class="spinner" aria-hidden="true"></div>
      <div>Connecting to the console… it builds its simulator first (about half a minute).</div>
    </div>
  {:else if app.mode === "operate"}
    <main class="operate">
      <Feed />
      <section class="stage" aria-label="the network">
        <div data-tour="kpis"><Kpis /></div>
        <div class="mapwrap" data-tour="map"><OperateMap /></div>
        <div data-tour="timeline"><Timeline /></div>
      </section>
      <Rail />
      {#if app.inspect !== null}
        <div class="inspect" data-tour="inspector"><Inspector n={app.inspect} /></div>
      {/if}
    </main>
    <footer data-tour="command">
      <CommandBar />
      <Drawer />
    </footer>
  {:else}
    <main class="racemain" data-tour="race"><RaceView /></main>
  {/if}
  {#if app.paletteOpen}<Palette />{/if}
  {#if app.tourOpen && app.state}<Tour />{/if}
</div>

<style>
  .shell { display: flex; flex-direction: column; height: 100vh; }
  .boot { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; padding: 0 16px; text-align: center; color: var(--muted); }
  .spinner { width: 28px; height: 28px; border-radius: 50%; border: 3px solid var(--line2); border-top-color: var(--cyan); animation: spin 0.9s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .operate { position: relative; flex: 1; min-height: 0; display: grid; grid-template-columns: 360px minmax(0, 1fr) 330px; }
  .stage { display: flex; flex-direction: column; min-height: 0; min-width: 0; container: stage / inline-size; }
  .mapwrap { position: relative; flex: 1; min-height: 260px; }
  .inspect { position: absolute; top: 0; right: 0; bottom: 0; width: min(480px, 100%); z-index: 25; }
  .inspect :global(.inspector) { position: absolute; inset: 0; width: 100%; }
  footer { border-top: 1px solid var(--line); background: var(--panel); }
  .racemain { flex: 1; min-height: 0; }
  @media (max-width: 1500px) { .operate { grid-template-columns: 320px minmax(0, 1fr) 300px; } }
  @media (max-width: 1180px) {
    .shell { height: auto; min-height: 100vh; }
    :global(body) { overflow: auto; }
    .operate { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
    .stage { grid-column: 1 / -1; order: -1; border-bottom: 1px solid var(--line); }
    .mapwrap { flex: none; height: min(62vw, 560px); }
    .operate :global(.feed .events) { max-height: 560px; }
    .inspect { position: fixed; }
    footer { position: sticky; bottom: 0; z-index: 20; } /* the command line stays in reach on a long page */
  }
  @media (max-width: 760px) {
    /* one column on a phone: the network, then the rail (where a question appears), then the feed */
    .operate { grid-template-columns: minmax(0, 1fr); }
    .operate :global(.rail) { order: 0; border-left: 0; border-bottom: 1px solid var(--line); max-height: none; }
    .operate :global(.feed) { order: 1; border-right: 0; }
    .operate :global(.feed .events) { max-height: 70vh; }
  }
</style>
