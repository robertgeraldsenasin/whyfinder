<script lang="ts">
  import { PIPS, rankLabel, rankName, SUITS, suitOf } from '../cards';
  import * as sfx from '../sfx';
  import { settings } from '../settings.svelte';
  import { colorAt, tier } from '../sky';
  import { app } from '../state.svelte';

  let { closeness }: { closeness: Float32Array | null } = $props();

  const result = $derived(app.result);
  const games = $derived(app.slice?.games ?? []);
  const n = $derived(result?.picks.length ?? 0);
  const firstVisible = $derived(n - app.landed);
  const suits = $derived(result ? result.explanations.map((e) => suitOf(e.attributions)) : []);

  function choose(t: number): void {
    app.selected = t;
    sfx.select();
  }

  function onKey(e: KeyboardEvent): void {
    if (!result) return;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') app.selected = (app.selected + 1) % n;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') app.selected = (app.selected - 1 + n) % n;
    else return;
    e.preventDefault();
    sfx.select();
    document.getElementById(`pick-${app.selected}`)?.focus();
  }
</script>

{#if result}
  <section class="panel list" aria-labelledby="hand-title">
    <div class="head">
      <h2 id="hand-title">Your hand</h2>
      {#if app.falling}
        <button class="btn ghost skip" onclick={() => app.skipFall++}>Skip</button>
      {:else}
        <span class="count">{n} cards</span>
      {/if}
    </div>
    <div role="region" aria-label="Your picks">
      <ol>
        {#each result.picks as p, t (p)}
          {@const c = closeness?.[p] ?? 0}
          {@const suit = suits[t] ?? 'hearts'}
          {#if t >= firstVisible}
            <li class:landing={app.falling}>
              <button
                id={`pick-${t}`}
                class="row"
                class:selected={app.selected === t && !app.falling}
                aria-pressed={app.selected === t}
                tabindex={app.selected === t ? 0 : -1}
                onclick={() => choose(t)}
                onkeydown={onKey}
              >
                <span class="mini {suit}" aria-hidden="true">
                  <span class="idx">{rankLabel(t)}</span>
                  <svg viewBox="0 0 24 24"><path d={PIPS[suit]} /></svg>
                </span>
                <span class="sr-only">{rankName(t)} of {SUITS[suit].name.toLowerCase()}:</span>
                <span class="name">{games[p].title}</span>
                <span class="tier">
                  <svg class="dot" viewBox="0 0 24 24" aria-hidden="true"><path d={PIPS.star} fill={colorAt(settings.palette, c)} /></svg>
                  <span>{tier(c).name}{#if result.variety[t]}<span class="variety">, picked for variety</span>{/if}</span>
                </span>
              </button>
            </li>
          {/if}
        {/each}
      </ol>
    </div>
    <p class="suits">
      <span class="h"><svg viewBox="0 0 24 24" aria-hidden="true"><path d={PIPS.hearts} /></svg>Hearts: {SUITS.hearts.plain}</span>
      <span class="c"><svg viewBox="0 0 24 24" aria-hidden="true"><path d={PIPS.clubs} /></svg>Clubs: {SUITS.clubs.plain}</span>
    </p>
  </section>
{/if}

<style>
  .list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding-bottom: var(--space-3);
  }
  .head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
  }
  h2 {
    font-size: 22px;
    line-height: 1;
  }
  .count {
    font-size: var(--text-xs);
    color: var(--muted);
  }
  .skip {
    padding: 4px 10px;
  }
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
  }
  li.landing {
    animation: dealt 560ms var(--ease-pop);
  }
  @keyframes dealt {
    0% {
      opacity: 0;
      transform: translate(26px, -14px) rotate(6deg);
      filter: brightness(2);
    }
    45% {
      opacity: 1;
      filter: brightness(1.5);
    }
    100% {
      transform: none;
      filter: none;
    }
  }
  .row {
    width: 100%;
    display: grid;
    grid-template-columns: 38px minmax(0, 1fr);
    grid-template-areas:
      'card name'
      'card tier';
    column-gap: var(--space-3);
    align-items: center;
    text-align: left;
    background: transparent;
    border: 0;
    border-bottom: 1px solid color-mix(in srgb, var(--line) 75%, transparent);
    padding: 7px 8px 6px 4px;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease-out);
  }
  .row:hover {
    background: color-mix(in srgb, var(--raised) 70%, transparent);
  }
  .row.selected {
    background: linear-gradient(90deg, color-mix(in srgb, var(--crimson) 22%, var(--raised)), var(--raised) 70%);
    box-shadow: inset 3px 0 0 var(--crimson);
  }
  /* A miniature card: the rank and the suit pip, printed on bone. */
  .mini {
    grid-area: card;
    width: 30px;
    height: 42px;
    border-radius: 4px;
    background: var(--bone);
    color: var(--crimson);
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-top: 5px;
    box-shadow: 0 2px 0 rgb(0 0 0 / 0.45);
    transition:
      transform 220ms var(--ease-pop),
      box-shadow 220ms var(--ease-out);
  }
  .mini.clubs {
    color: var(--club);
  }
  .idx {
    font-family: var(--font-poster);
    font-size: 15px;
    line-height: 1;
  }
  .mini svg {
    width: 11px;
    height: 11px;
    margin-top: 3px;
    fill: currentColor;
  }
  .row:hover .mini {
    transform: translateY(-2px);
  }
  .row.selected .mini {
    transform: translate(-2px, -4px) rotate(-7deg);
    box-shadow: 3px 3px 0 var(--crimson);
  }
  .name {
    grid-area: name;
    padding-top: 2px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .tier {
    grid-area: tier;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-size: var(--text-xs);
    color: var(--muted);
  }
  .dot {
    width: 10px;
    height: 10px;
    flex: none;
  }
  .variety {
    color: var(--link);
  }
  .suits {
    margin: var(--space-2) 0 0;
    display: flex;
    flex-wrap: wrap;
    gap: 4px var(--space-4);
    font-size: var(--text-xs);
  }
  .suits span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .suits svg {
    width: 12px;
    height: 12px;
    fill: currentColor;
  }
  .suits .h {
    color: var(--crimson-text);
  }
  .suits .c {
    color: var(--quantum-text);
  }
</style>
