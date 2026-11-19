<script lang="ts">
  import { PIPS } from '../cards';
  import Describe from '../components/Describe.svelte';
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
    <div class="sky" data-stage></div>
    <div class="hero">
      <h1 class="lockup">
        <span class="halo" aria-hidden="true"></span>
        <Wordmark size="var(--lockup)" ribbon="Find your next game. Know why." />
      </h1>
      <p class="lead">
        <strong>Name the games you love.</strong> Ten picks are dealt into your sky from Steam's 500 most-played games, and every
        one shows its hand: the exact reasons, and what players say.
      </p>
      <GameSearch size="hero" />
      <Describe size="hero" deal />
      <div class="presets">
        <p id="start-from">Or start from someone else's hand</p>
        <ul class="fan" aria-labelledby="start-from">
          {#each presets as p, k (p.name)}
            <li style:--k={k - (presets.length - 1) / 2}>
              <button class="preset on-bone" disabled={!app.ready} onclick={() => usePreset(p.items)}>
                <svg class="corner tl" viewBox="0 0 24 24" aria-hidden="true"><path d={PIPS.star} /></svg>
                <span class="pname display">{p.name}</span>
                <span class="rule" aria-hidden="true"></span>
                <span class="ptitles">{p.items.map((x) => games[x.index].title).join(', ')}</span>
                <svg class="corner br" viewBox="0 0 24 24" aria-hidden="true"><path d={PIPS.star} /></svg>
              </button>
            </li>
          {/each}
        </ul>
      </div>
    </div>
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
          {app.history.length === 1 ? 'One star in your sky. Add two or three more for a sharper hand, or find your next game now.' : 'Your cast is ready. Press Find my next game and ten cards are dealt.'}
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
    min-height: calc(100dvh - 68px);
    display: grid;
    justify-items: center;
    align-content: center;
    padding: var(--space-2) var(--space-5) var(--space-6);
    text-align: center;
    pointer-events: none;
  }
  .sky {
    position: absolute;
    inset: 0;
  }
  /* A pool of dark behind the words, so stars never sit under text. */
  .title::before {
    content: '';
    position: absolute;
    left: 50%;
    top: 47%;
    width: min(1120px, 130vw);
    height: 780px;
    transform: translate(-50%, -50%);
    background: radial-gradient(closest-side, rgb(11 7 16 / 0.86), rgb(11 7 16 / 0.55) 62%, transparent);
    pointer-events: none;
  }
  .hero {
    position: relative;
    pointer-events: auto;
    width: min(760px, 100%);
    display: flex;
    flex-direction: column;
    align-items: center;
    animation: curtain 900ms var(--ease-out);
  }
  @keyframes curtain {
    from {
      opacity: 0;
      transform: translateY(18px) scale(0.98);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
  .lockup {
    --lockup: clamp(60px, 9vw, 132px);
    position: relative;
    max-width: 100%;
  }
  .halo {
    position: absolute;
    z-index: -1;
    left: 2%;
    top: -22%;
    width: 46%;
    height: 112%;
    color: var(--crimson-hot);
    opacity: 0.34;
    background-image: var(--halftone);
    background-size: 10px 10px;
    -webkit-mask: radial-gradient(closest-side, #000 20%, transparent);
    mask: radial-gradient(closest-side, #000 20%, transparent);
  }
  .lead {
    max-width: 56ch;
    margin: var(--space-5) auto 0;
    color: var(--muted);
    font-size: 19px;
    line-height: 1.55;
  }
  .lead strong {
    color: var(--text);
    font-weight: 600;
  }
  .hero :global(.search.hero) {
    width: min(620px, 100%);
    margin-top: var(--space-6);
  }
  .presets {
    width: 100%;
  }
  .presets p {
    margin: var(--space-6) 0 var(--space-3);
    font-size: 15px;
    color: var(--muted);
  }
  .fan {
    list-style: none;
    margin: 0;
    padding: 0 0 var(--space-4);
    display: flex;
    justify-content: center;
  }
  .fan li {
    position: relative;
    margin: 0 -4px;
  }
  .fan li:hover,
  .fan li:focus-within {
    z-index: 5;
  }
  .preset {
    position: relative;
    width: 168px;
    height: 214px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 9px;
    padding: 30px 22px 26px;
    border: 0;
    border-radius: 10px;
    text-align: center;
    cursor: pointer;
    box-shadow:
      0 1px 0 1px rgb(0 0 0 / 0.3),
      0 18px 30px -12px rgb(0 0 0 / 0.85);
    transform: rotate(calc(var(--k) * 6deg)) translateY(calc(var(--k) * var(--k) * 8px));
    transition:
      transform 240ms var(--ease-pop),
      box-shadow 240ms var(--ease-out);
  }
  .preset::before {
    content: '';
    position: absolute;
    inset: 7px;
    border: 1px solid rgb(26 14 24 / 0.22);
    border-radius: 6px;
    pointer-events: none;
  }
  .preset:hover:not([disabled]),
  .preset:focus-visible {
    transform: rotate(0) translateY(-18px) scale(1.04);
    box-shadow:
      0 0 0 3px var(--crimson),
      0 26px 40px -12px rgb(0 0 0 / 0.9);
  }
  .preset[disabled] {
    cursor: progress;
    filter: saturate(0.6) brightness(0.85);
  }
  .corner {
    position: absolute;
    width: 12px;
    height: 12px;
    fill: var(--crimson);
  }
  .tl {
    left: 14px;
    top: 14px;
  }
  .br {
    right: 14px;
    bottom: 14px;
  }
  .pname {
    font-size: 22px;
    line-height: 1.1;
  }
  .rule {
    width: 34px;
    height: 2px;
    margin: 0 auto;
    background: var(--crimson);
  }
  .ptitles {
    font-size: var(--text-xs);
    line-height: 1.35;
    color: var(--on-bone-muted);
  }

  .discover {
    position: relative;
    z-index: 2;
    display: grid;
    grid-template-columns: 340px minmax(0, 1fr);
    grid-template-areas: 'left stage';
    gap: var(--space-5);
    height: calc(100dvh - 68px);
    padding: 0 var(--space-5) var(--space-5);
    pointer-events: none;
  }
  .discover.has-detail {
    grid-template-columns: 340px minmax(0, 1fr) 430px;
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
    max-width: 46ch;
    text-align: center;
    padding: 10px 20px 8px;
    background: var(--surface-solid);
    border: var(--border);
    box-shadow: 4px 4px 0 var(--crimson);
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
    .lockup {
      --lockup: clamp(48px, 15vw, 96px);
    }
  }
  @media (max-width: 760px) {
    .title {
      padding: var(--space-3) var(--space-4) var(--space-6);
    }
    .discover,
    .discover.has-detail {
      grid-template-columns: minmax(0, 1fr);
      grid-template-areas: 'stage' 'left' 'right';
      grid-template-rows: 46vh auto auto;
      height: auto;
      padding: 0 var(--space-3) var(--space-4);
    }
    .lead {
      font-size: var(--text-md);
    }
    .fan {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px 10px;
    }
    .fan li {
      margin: 0;
    }
    .preset {
      width: 100%;
      height: 176px;
      padding: 26px 16px 22px;
      transform: rotate(calc(var(--k) * 1.6deg));
    }
  }
</style>
