<script lang="ts">
  import GameSearch from '../components/GameSearch.svelte';
  import Wordmark from '../components/Wordmark.svelte';
  import PickDetail from '../components/PickDetail.svelte';
  import SkyTray from '../components/SkyTray.svelte';
  import StarList from '../components/StarList.svelte';
  import * as sfx from '../sfx';
  import { closeness as closenessOf } from '../sky';
  import { app, type SceneLine } from '../state.svelte';

  const games = $derived(app.slice?.games ?? []);
  const result = $derived(app.result && !app.stale ? app.result : null);
  const closeness = $derived(result ? closenessOf(result.scores, result.history.map(([j]) => j)) : null);
  const landedAll = $derived(!!result && app.landed >= result.picks.length);

  const PRESETS: [string, string[], number[]][] = [
    ['Puzzles and stories', ['Portal 2', 'Undertale', 'The Stanley Parable'], [40, 12, 3]],
    ['Survival crews', ['Rust', 'DayZ', 'Arma 3'], [300, 120, 80]],
    ['Roguelike runs', ['FTL: Faster Than Light', 'The Binding of Isaac', 'XCOM: Enemy Unknown'], [60, 90, 45]],
    ['Grand strategy', ["Sid Meier's Civilization® V", 'Stellaris', 'Mount & Blade: Warband'], [400, 60, 90]],
  ];
  const presets = $derived(
    PRESETS.map(([name, titles, hours]) => ({
      name,
      items: titles.map((t, k) => ({ index: games.findIndex((g) => g.title === t), hours: hours[k] })).filter((x) => x.index >= 0),
    })).filter((p) => p.items.length >= 2),
  );

  function usePreset(items: { index: number; hours: number }[]): void {
    sfx.unlock();
    app.history = items.map((x) => ({ ...x }));
    void app.find();
  }

  // What the sky draws in Discover: your stars, the picks, and the reasons for the selected pick.
  $effect(() => {
    const history = app.history.map((h) => h.index);
    if (!result) {
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
        closeness: null,
        fall: null,
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
      focus: [...result.history.map(([j]) => j), ...result.picks],
      history: result.history.map(([j]) => j),
      picks: result.picks,
      selected: e.pick,
      lines,
      glow: null,
      hubs: related ? [related.via!] : [],
      hubGlow: null,
      dim: 0.2,
      key: `discover:${app.resultFor}:${app.selected}`,
      closeness,
      fall: result.picks.join(','),
    };
  });
</script>

{#if !app.history.length}
  <div class="title">
    <div class="hero">
      <h1 class="lockup"><Wordmark size="var(--lockup)" line="— 500 STARS —" /></h1>
      <p class="lead">
        <strong>Name the games you love. Watch where your next one falls.</strong> Every star is one of Steam's 500
        most-played games, placed by the players they share. Ten picks fall into your sky, each with the exact reasons and
        what players say.
      </p>
      <GameSearch size="hero" />
      <div class="presets">
        <p id="start-from">Or start from a sky someone else might have</p>
        <ul aria-labelledby="start-from">
          {#each presets as p (p.name)}
            <li>
              <button class="preset" disabled={!app.ready} onclick={() => usePreset(p.items)}>
                <span class="pname">{p.name}</span>
                <span class="ptitles">{p.items.map((x) => games[x.index].title).join(', ')}</span>
              </button>
            </li>
          {/each}
        </ul>
      </div>
    </div>
    <div class="sky" data-stage></div>
  </div>
{:else}
  <div class="discover" class:has-detail={!!result}>
    <div class="left">
      <SkyTray />
      <StarList {closeness} />
    </div>
    <div class="stage" data-stage>
      {#if !result && !app.running}
        <p class="hint">
          {app.history.length === 1 ? 'One star in your sky. Add two or three more for sharper picks, or find your next game now.' : 'Your constellation is ready. Press Find my next game.'}
        </p>
      {/if}
    </div>
    {#if result}
      <div class="right">
        {#if landedAll}
          <PickDetail {closeness} />
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .title {
    position: relative;
    z-index: 2;
    min-height: calc(100dvh - 72px);
    display: grid;
    grid-template-columns: minmax(0, 46%) minmax(0, 1fr);
    align-items: center;
    padding: 0 var(--space-5) var(--space-6) clamp(24px, 6vw, 96px);
    pointer-events: none;
  }
  .sky {
    align-self: stretch;
  }
  .hero {
    pointer-events: auto;
    max-width: 620px;
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
    animation: dawn 1100ms var(--ease-out);
  }
  @keyframes dawn {
    from {
      opacity: 0;
      transform: translateY(14px);
      filter: blur(6px);
    }
    to {
      opacity: 1;
      transform: none;
      filter: none;
    }
  }
  .lockup {
    --lockup: clamp(46px, 5.4vw, 86px);
    align-self: flex-start;
    max-width: 100%;
    text-shadow: 0 0 40px rgb(7 11 30 / 0.9);
  }
  .lead strong {
    display: block;
    margin-bottom: var(--space-2);
    font-family: var(--font-display);
    font-weight: 400;
    font-size: var(--text-xl);
    line-height: 1.25;
    color: var(--text);
  }
  .lead {
    margin: 0;
    max-width: 52ch;
    color: var(--muted);
    font-size: var(--text-lg);
    line-height: 1.5;
    text-shadow: 0 0 20px rgb(7 11 30 / 1);
  }
  .presets p {
    margin: 0 0 var(--space-3);
    font-size: var(--text-sm);
    color: var(--muted);
  }
  .presets ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-2);
  }
  .preset {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 3px;
    text-align: left;
    padding: 11px 14px 9px;
    border: 1px solid var(--line);
    border-left: 2px solid var(--frame-line);
    background: color-mix(in srgb, var(--deep) 88%, transparent);
    cursor: pointer;
    transition:
      border-color var(--dur-fast) var(--ease-out),
      background var(--dur-fast) var(--ease-out);
  }
  .preset:hover:not([disabled]) {
    border-color: color-mix(in srgb, var(--gold) 50%, transparent);
    border-left-color: var(--gold);
    background: var(--raised);
  }
  .preset[disabled] {
    opacity: 0.6;
    cursor: progress;
  }
  .pname {
    font-family: var(--font-display);
    font-size: var(--text-lg);
  }
  .ptitles {
    font-size: var(--text-xs);
    color: var(--muted);
  }

  .discover {
    position: relative;
    z-index: 2;
    display: grid;
    grid-template-columns: 340px minmax(0, 1fr);
    grid-template-areas: 'left stage';
    gap: var(--space-5);
    height: calc(100dvh - 72px);
    padding: 0 var(--space-5) var(--space-5);
    pointer-events: none;
  }
  .discover.has-detail {
    grid-template-columns: 340px minmax(0, 1fr) 420px;
    grid-template-areas: 'left stage right';
  }
  .left,
  .right {
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
    scrollbar-color: var(--line) transparent;
    padding-bottom: var(--space-2);
  }
  .right {
    grid-area: right;
    display: flex;
    flex-direction: column;
  }
  .stage {
    grid-area: stage;
    position: relative;
    display: flex;
    align-items: flex-end;
    justify-content: center;
  }
  .hint {
    margin: 0 0 var(--space-4);
    max-width: 44ch;
    text-align: center;
    padding: 9px 18px 7px;
    background: var(--surface-solid);
    border: 1px solid var(--frame-line);
    color: var(--muted);
    font-size: var(--text-sm);
    animation: rise var(--dur-mid) var(--ease-out);
  }
  @media (max-width: 1180px) {
    .discover.has-detail {
      grid-template-columns: 320px minmax(0, 1fr);
      grid-template-areas:
        'left stage'
        'right right';
      grid-template-rows: calc(100dvh - 96px) auto;
      height: auto;
    }
    .right {
      max-width: 720px;
    }
  }
  @media (max-width: 900px) {
    .title {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: 34vh auto;
      padding: 0 var(--space-4) var(--space-6);
    }
    .sky {
      grid-row: 1;
    }
    .lockup {
      --lockup: clamp(34px, 10.6vw, 72px);
      align-self: center;
    }
  }
  @media (max-width: 760px) {
    .discover,
    .discover.has-detail {
      grid-template-columns: minmax(0, 1fr);
      grid-template-areas: 'stage' 'left' 'right';
      grid-template-rows: 46vh auto auto;
      height: auto;
      padding: 0 var(--space-3) var(--space-4);
    }
    .presets ul {
      grid-template-columns: minmax(0, 1fr);
    }
    .lead {
      font-size: var(--text-md);
    }
  }
</style>
