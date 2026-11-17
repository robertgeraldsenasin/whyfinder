<script lang="ts">
  import { list, num, pct, price, rank } from '../format';
  import { app } from '../state.svelte';

  const result = $derived(app.result);
  const games = $derived(app.slice?.games ?? []);
  const hubs = $derived(app.ready?.hubs ?? []);
  const e = $derived(result?.explanations[app.selected] ?? null);
  const game = $derived(e ? games[e.pick] : null);
  const total = $derived(e ? e.attributions.reduce((s, a) => s + Math.abs(a.total), 0) : 0);
  const sum = $derived(e ? e.attributions.reduce((s, a) => s + a.total, 0) : 0);
  const scoreRank = $derived(e && result ? result.candidates.indexOf(e.pick) + 1 : 0);
  const removedNames = $derived(e ? e.counterfactual.removed.map((j) => games[j].title) : []);
  const wholeList = $derived(!!e && result !== null && e.counterfactual.removed.length === result.history.length);

  function hubName(node: number | null): string {
    return node === null ? '' : (hubs[node - games.length]?.name ?? '');
  }
</script>

{#if e && game && result}
  <section class="panel hud why" aria-labelledby="why-title" aria-live="polite">
    <p class="micro">Why this pick</p>
    {#key e.pick}
      <div class="fade">
        <h2 id="why-title">{game.title}</h2>
        <p class="meta">
          Pick {rank(e.rank)} · {game.year ?? 'year n/a'} · {price(game.price)}{#if game.tags.length}
            · {game.tags.slice(0, 3).join(' · ')}{/if}
        </p>
        {#if e.variety}
          <p class="variety">
            <span class="chip link">Kept for variety</span>
            Not in the top 10 by score alone (it ranks {scoreRank} by score); the DPP re-ranker kept it to widen your list.
          </p>
        {/if}

        <h3 class="micro">What drove it</h3>
        <ul class="bars">
          {#each e.attributions as a (a.game)}
            {@const share = total > 0 ? Math.abs(a.total) / total : 0}
            {@const easeShare = Math.abs(a.total) > 0 ? Math.max(0, a.ease / a.total) : 0}
            <li>
              <span class="who">{games[a.game].title}</span>
              <span class="track" aria-hidden="true">
                <span class="fill" class:neg={a.total < 0} style:width={`${share * 100}%`}>
                  <span class="ease" style:width={`${easeShare * 100}%`}></span>
                </span>
              </span>
              <span class="val mono" class:neg={a.total < 0}>{a.total < 0 ? '−' : ''}{pct(sum !== 0 ? Math.abs(a.total) / Math.abs(sum) : 0)}</span>
            </li>
          {/each}
        </ul>
        <p class="legend micro">
          <span class="key ease" aria-hidden="true"></span> co-play (EASE^R)
          <span class="key ppr" aria-hidden="true"></span> graph (PageRank)
        </p>
        <p class="check micro" title="The contributions add up to the score exactly: no approximation.">
          Σ contributions {num(sum)} = score {num(e.score)} · shares are exact
        </p>

        <div class="cf">
          {#if wholeList}
            <p>Only removing your whole list drops this pick: every game you added pulls toward it.</p>
          {:else}
            <p>Without <strong>{list(removedNames)}</strong> in your list, this pick drops out of your top 10.</p>
          {/if}
          <p class="micro">
            {removedNames.length === 1 ? 'A single game' : 'Irreducible set'} · checked by re-running the whole pipeline ({e.counterfactual.runs}
            {e.counterfactual.runs === 1 ? 'run' : 'runs'})
          </p>
        </div>

        {#if e.paths.length}
          <h3 class="micro">Related by</h3>
          <ul class="paths">
            {#each e.paths as p, k (k)}
              <li>
                {#if p.kind === 'co-play'}
                  often played together with <strong>{games[p.source].title}</strong>
                {:else if p.kind === 'tag'}
                  shares the tag <strong>{hubName(p.via)}</strong> with {games[p.source].title}
                {:else if p.kind === 'developer'}
                  same developer as {games[p.source].title}: <strong>{hubName(p.via)}</strong>
                {:else}
                  same publisher as {games[p.source].title}: <strong>{hubName(p.via)}</strong>
                {/if}
              </li>
            {/each}
          </ul>
        {/if}

        <h3 class="micro">In words</h3>
        <p class="words">
          Sentences grounded in real reviews arrive with the RAG layer (M3). Until then, everything above is computed, not
          written.
        </p>
        <button class="btn ghost how" onclick={() => ((app.stage = 6), app.go('hood'))}>See how this was computed →</button>
      </div>
    {/key}
  </section>
{/if}

<style>
  .why {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    max-height: 100%;
    overflow-y: auto;
    scrollbar-width: thin;
  }
  .fade {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    animation: rise var(--dur-fast) var(--ease-out);
  }
  h2 {
    font-size: var(--text-xl);
  }
  h3 {
    margin-top: var(--space-2);
  }
  .meta {
    margin: 0;
    color: var(--muted);
    font-size: var(--text-sm);
  }
  .variety {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--muted);
  }
  .bars {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .bars li {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr) 46px;
    align-items: center;
    gap: 10px;
    font-size: var(--text-sm);
  }
  .who {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .track {
    height: 6px;
    border-radius: 3px;
    background: var(--raised);
    overflow: hidden;
  }
  .fill {
    display: block;
    height: 100%;
    border-radius: 3px;
    background: color-mix(in srgb, var(--link) 45%, transparent);
    transition: width 400ms var(--ease-out);
  }
  .fill .ease {
    display: block;
    height: 100%;
    background: var(--link);
  }
  .fill.neg {
    background: var(--bad);
  }
  .fill.neg .ease {
    background: var(--bad);
  }
  .val {
    text-align: right;
    font-size: var(--text-xs);
  }
  .val.neg {
    color: var(--bad);
  }
  .legend {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0;
    flex-wrap: wrap;
  }
  .key {
    display: inline-block;
    width: 10px;
    height: 6px;
    border-radius: 2px;
    margin-left: 6px;
  }
  .key.ease {
    background: var(--link);
    margin-left: 0;
  }
  .key.ppr {
    background: color-mix(in srgb, var(--link) 45%, transparent);
  }
  .check {
    margin: 0;
    color: var(--good);
  }
  .cf {
    background: var(--raised);
    border-left: 3px solid var(--pick);
    border-radius: 6px;
    padding: var(--space-3) var(--space-4);
  }
  .cf p {
    margin: 0;
    font-size: var(--text-sm);
  }
  .cf p.micro {
    margin-top: 6px;
    font-size: var(--text-xs);
  }
  .paths {
    margin: 0;
    padding-left: 18px;
    font-size: var(--text-sm);
    color: var(--muted);
  }
  .paths strong {
    color: var(--text);
  }
  .words {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--muted);
  }
  .how {
    align-self: flex-start;
    padding-left: 0;
    color: var(--link);
  }
</style>
