<script lang="ts">
  import { onMount } from 'svelte';
  import Atlas from './lib/components/Atlas.svelte';
  import InspectCard from './lib/components/InspectCard.svelte';
  import TopBar from './lib/components/TopBar.svelte';
  import { app, viewFromHash } from './lib/state.svelte';
  import Architecture from './lib/views/Architecture.svelte';
  import Discover from './lib/views/Discover.svelte';
  import UnderTheHood from './lib/views/UnderTheHood.svelte';

  const phases: Record<string, string> = {
    cholesky: 'Factoring G + λI (Cholesky)',
    invert: 'Inverting for EASE^R',
    weights: 'Item-item weights B',
    pi: 'PageRank rows',
  };

  onMount(() => {
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    app.reducedMotion = motion.matches;
    motion.addEventListener('change', (e) => (app.reducedMotion = e.matches));
    app.view = viewFromHash(location.hash);
    const onHash = () => (app.view = viewFromHash(location.hash));
    window.addEventListener('popstate', onHash);
    window.addEventListener('hashchange', onHash);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') app.inspect = null;
    };
    window.addEventListener('keydown', onKey);
    void app.load(import.meta.env.BASE_URL);
    return () => {
      window.removeEventListener('popstate', onHash);
      window.removeEventListener('hashchange', onHash);
      window.removeEventListener('keydown', onKey);
    };
  });
</script>

<a class="skip" href="#main">Skip to content</a>
<Atlas />
<div class="shell">
  <TopBar />
  <main id="main" tabindex="-1">
    {#if app.error}
      <div class="panel status" role="alert">
        <p class="micro">Something went wrong</p>
        <p>{app.error}</p>
      </div>
    {:else if !app.ready}
      <div class="panel status hud" role="status" aria-live="polite">
        <p class="micro">Starting the engine in your browser</p>
        <p>{app.progress ? phases[app.progress.phase] ?? app.progress.phase : 'Loading 500 games and their co-play matrix…'}</p>
        {#if app.progress}
          <div class="meter" aria-hidden="true"><span style:width={`${(app.progress.done / app.progress.total) * 100}%`}></span></div>
        {/if}
      </div>
    {:else if app.view === 'discover'}
      <Discover />
    {:else if app.view === 'hood'}
      <UnderTheHood />
    {:else}
      <Architecture />
    {/if}
  </main>
</div>
<InspectCard />

<style>
  .shell {
    position: relative;
    z-index: 2;
    pointer-events: none;
  }
  .shell :global(header) {
    pointer-events: auto;
  }
  main:focus {
    outline: none;
  }
  .status {
    pointer-events: auto;
    max-width: 420px;
    margin: 18vh auto 0;
  }
  .status p {
    margin: 0 0 var(--space-2);
  }
  .meter {
    height: 3px;
    background: var(--raised);
    border-radius: 2px;
    overflow: hidden;
  }
  .meter span {
    display: block;
    height: 100%;
    background: var(--link);
    transition: width 120ms linear;
  }
  .skip {
    position: absolute;
    left: -999px;
    top: 8px;
    z-index: 100;
    background: var(--surface);
    color: var(--text);
    padding: 8px 12px;
    border-radius: 8px;
  }
  .skip:focus {
    left: 8px;
  }
</style>
