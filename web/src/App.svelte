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
    cholesky: 'Learning which games are played together',
    invert: 'Learning which games are played together',
    weights: 'Weighing every pair of games',
    pi: 'Tracing links between games',
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
        <h1>The sky did not load</h1>
        <p>{app.error}</p>
        <p class="micro">Reload the page to try again.</p>
      </div>
    {:else if app.view === 'discover' && (app.ready || app.history.length === 0)}
      <Discover />
    {:else if !app.ready}
      <div class="status" role="status" aria-live="polite">
        <h1>Setting the stage</h1>
        <p>{app.progress ? (phases[app.progress.phase] ?? app.progress.phase) : 'Loading 500 games'}</p>
        <div class="meter" aria-hidden="true"><span style:width={`${app.progress ? (app.progress.done / app.progress.total) * 100 : 4}%`}></span></div>
      </div>
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
    max-width: 440px;
    margin: 22vh auto 0;
    text-align: center;
  }
  .status h1 {
    font-size: 40px;
    margin-bottom: var(--space-2);
    transform: skewX(-8deg);
    text-shadow: 3px 3px 0 var(--crimson-deep);
  }
  .status p {
    margin: 0 0 var(--space-3);
    color: var(--muted);
  }
  .meter {
    height: 8px;
    background: var(--velvet);
    border: var(--border);
    transform: skewX(-20deg);
    overflow: hidden;
  }
  .meter span {
    display: block;
    height: 100%;
    background: repeating-linear-gradient(90deg, var(--crimson) 0 10px, var(--crimson-hot) 10px 14px);
    transition: width 160ms linear;
  }
  .skip {
    position: absolute;
    left: -999px;
    top: 8px;
    z-index: 100;
    background: var(--surface-solid);
    color: var(--text);
    padding: 8px 12px;
    border-radius: 0;
  }
  .skip:focus {
    left: 8px;
  }
</style>
