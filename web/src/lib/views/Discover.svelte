<script lang="ts">
  import GamePicker from '../components/GamePicker.svelte';
  import PickRail from '../components/PickRail.svelte';
  import WhyPanel from '../components/WhyPanel.svelte';
  import { ms } from '../format';
  import { app, type SceneLine } from '../state.svelte';

  // What the atlas draws in Discover: your stars, the picks, and the reasons for the selected pick.
  $effect(() => {
    const result = app.result;
    const history = app.history.map((h) => h.index);
    if (!result || app.stale) {
      app.scene = {
        focus: history,
        history,
        picks: [],
        selected: null,
        lines: [],
        glow: null,
        hubs: [],
        hubGlow: null,
        dim: 0,
        key: `discover:${history.join(',')}`,
      };
      return;
    }
    const e = result.explanations[app.selected];
    const total = e.attributions.reduce((s, a) => s + Math.abs(a.total), 0) || 1;
    const lines: SceneLine[] = e.attributions.map((a) => ({
      from: a.game,
      to: e.pick,
      share: Math.abs(a.total) / total,
      kind: a.total < 0 ? 'negative' : 'reason',
    }));
    const related = e.paths.find((p) => p.via !== null);
    if (related) lines.push({ from: related.source, to: related.target, share: 0, kind: 'related', hub: related.via! });
    app.scene = {
      focus: [...result.history.map(([j]) => j), e.pick],
      history: result.history.map(([j]) => j),
      picks: result.picks,
      selected: e.pick,
      lines,
      glow: null,
      hubs: related ? [related.via!] : [],
      hubGlow: null,
      dim: 0.25,
      key: `discover:${app.resultFor}:${app.selected}`,
    };
  });

  const timings = $derived(app.result?.timings);
</script>

<div class="discover">
  <div class="left">
    <GamePicker />
    {#if app.ready}
      <p class="engine micro" aria-live="polite">
        Engine live in your browser · EASE^R {ms(app.ready.timings.ease)} · graph {app.ready.nodes.toLocaleString('en-US')} nodes
        {#if timings}· picks + reasons {ms(timings.score + timings.explain + timings.pi)}{/if}
      </p>
    {/if}
  </div>

  <div class="stage" data-stage>
    {#if !app.history.length}
      <div class="hero">
        <h1>Find your next game. <span>Know why.</span></h1>
        <p>
          Every star is one of the 500 most-played Steam games. Add a few you love: a glass-box recommender runs right
          here, and every line it draws is an exact reason.
        </p>
      </div>
    {:else if !app.result}
      <p class="hint micro">{app.history.length} {app.history.length === 1 ? 'star' : 'stars'} lit · press “Find my picks”</p>
    {/if}
  </div>

  <div class="right">
    <WhyPanel />
  </div>

  <div class="bottom">
    <PickRail />
  </div>
</div>

<style>
  .discover {
    position: relative;
    z-index: 2;
    display: grid;
    grid-template-columns: 300px minmax(0, 1fr) 360px;
    grid-template-rows: minmax(0, 1fr) auto;
    grid-template-areas:
      'left stage right'
      'left bottom right';
    gap: var(--space-4) var(--space-5);
    height: calc(100dvh - 64px);
    padding: 0 var(--space-5) var(--space-5);
    pointer-events: none;
  }
  .left,
  .right,
  .bottom {
    pointer-events: auto;
    min-height: 0;
  }
  .left {
    grid-area: left;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    overflow-y: auto;
    scrollbar-width: thin;
  }
  .right {
    grid-area: right;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .stage {
    grid-area: stage;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .bottom {
    grid-area: bottom;
    min-width: 0;
  }
  .engine {
    margin: 0;
    padding: 0 var(--space-2);
    font-size: 10px;
    line-height: 1.6;
  }
  .hero {
    max-width: 520px;
    text-align: center;
    padding: var(--space-5) var(--space-6);
    background: color-mix(in srgb, var(--bg) 82%, transparent);
    border-radius: 16px;
    animation: rise 400ms var(--ease-out);
  }
  .hero h1 {
    font-size: clamp(28px, 3.4vw, 44px);
    letter-spacing: -0.02em;
  }
  .hero h1 span {
    color: var(--pick);
  }
  .hero p {
    color: var(--muted);
    margin: var(--space-3) 0 0;
  }
  .hint {
    position: absolute;
    bottom: var(--space-3);
    left: 50%;
    transform: translateX(-50%);
    background: var(--surface);
    border: var(--border);
    border-radius: var(--radius-pill);
    padding: 4px 12px;
    margin: 0;
  }
  @media (max-width: 1100px) {
    .discover {
      grid-template-columns: 280px minmax(0, 1fr);
      grid-template-areas:
        'left stage'
        'left bottom'
        'right right';
      height: auto;
      min-height: calc(100dvh - 64px);
      grid-template-rows: 60vh auto auto;
    }
  }
  @media (max-width: 760px) {
    .discover {
      grid-template-columns: minmax(0, 1fr);
      grid-template-areas: 'stage' 'left' 'bottom' 'right';
      grid-template-rows: 48vh auto auto auto;
      padding: 0 var(--space-3) var(--space-4);
    }
    .hero {
      padding: var(--space-4);
    }
  }
</style>
