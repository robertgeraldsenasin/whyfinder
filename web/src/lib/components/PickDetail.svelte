<script lang="ts">
  import { sharedTerms, topTerms, type Voice, voices } from '../evidence';
  import { list, num, pct, price, studio } from '../format';
  import { settings } from '../settings.svelte';
  import { colorAt, gradient, tier } from '../sky';
  import { app } from '../state.svelte';

  let { closeness }: { closeness: Float32Array | null } = $props();

  const result = $derived(app.result);
  const games = $derived(app.slice?.games ?? []);
  const hubs = $derived(app.ready?.hubs ?? []);
  const e = $derived(result?.explanations[app.selected] ?? null);
  const game = $derived(e ? games[e.pick] : null);
  const c = $derived(e && closeness ? closeness[e.pick] : 0);
  const t = $derived(tier(c));
  const sum = $derived(e ? e.attributions.reduce((s, a) => s + a.total, 0) : 0);
  const absTotal = $derived(e ? e.attributions.reduce((s, a) => s + Math.abs(a.total), 0) : 0);
  const scoreRank = $derived(e && result ? result.candidates.indexOf(e.pick) + 1 : 0);
  const removedNames = $derived(e ? e.counterfactual.removed.map((j) => games[j].title) : []);
  const wholeList = $derived(!!e && !!result && e.counterfactual.removed.length === result.history.length);
  const order = $derived(e ? e.attributions.filter((a) => a.total > 0).map((a) => a.game) : []);
  const ev = $derived(game && app.evidence ? app.evidence.games[String(game.id)] : undefined);
  const said = $derived(voices(ev, order));
  const shared = $derived(
    e && app.evidence ? sharedTerms(ev, order.map((j) => app.evidence!.games[String(games[j].id)])) : [],
  );
  const terms = $derived(shared.length >= 2 ? shared : topTerms(ev, 8));
  let artFailed = $state(false);
  $effect(() => {
    void e?.pick;
    artFailed = false;
  });

  function hubName(node: number | null): string {
    return node === null ? '' : (hubs[node - games.length]?.name ?? '');
  }
  function ordinal(n: number): string {
    const s = ['th', 'st', 'nd', 'rd'];
    const v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
  }
</script>

{#snippet quote(q: Voice, others: string[])}
  <figure class="quote">
    <blockquote>{q.text}</blockquote>
    <figcaption>
      {Math.round(q.hours).toLocaleString('en-US')} hours on record{#if q.year}, reviewed in {q.year}{/if}{#if others.length}. Also
        played {list(others)}{/if}.
    </figcaption>
  </figure>
{/snippet}

{#if e && game && result}
  <section class="panel hud detail" aria-labelledby="pick-title">
    <p class="sr-only" aria-live="polite">Pick {e.rank + 1}: {game.title}</p>
    {#key e.pick}
      <div class="enter">
        <figure class="art">
          {#if !artFailed}
            <img
              src={`https://cdn.akamai.steamstatic.com/steam/apps/${game.id}/header.jpg`}
              alt=""
              width="460"
              height="215"
              onerror={() => (artFailed = true)}
            />
          {:else}
            <div class="plate" aria-hidden="true"><span class="display">{game.title}</span></div>
          {/if}
          <figcaption class="tier-pill" style:--tier={colorAt(settings.palette, c)}>
            <span class="dot" aria-hidden="true"></span>{t.name}
          </figcaption>
        </figure>

        <header>
          <p class="rank">Pick {e.rank + 1} of {result.picks.length}</p>
          <h2 id="pick-title">{game.title}</h2>
          <p class="facts">
            {#if game.developer}<span>{studio(game.developer)}</span>{/if}
            {#if game.year}<span>{game.year}</span>{/if}
            <span>{price(game.price)}</span>
          </p>
          <div class="actions">
            <a class="btn primary steam" href={`https://store.steampowered.com/app/${game.id}`} target="_blank" rel="noreferrer">
              View on Steam
            </a>
            <button class="btn ghost" onclick={() => ((app.stage = 6), app.go('hood'))}>How this was worked out</button>
          </div>
        </header>

        <div class="closeness">
          <div class="scale" style:background={gradient(settings.palette)} aria-hidden="true">
            <span class="marker" style:left={`${c * 100}%`}></span>
          </div>
          <p><strong>{t.name}</strong>: {t.plain}.</p>
        </div>

        {#if e.variety}
          <p class="variety">
            <strong>Picked for variety.</strong> By score alone it ranks {ordinal(scoreRank)}; it is here so your ten are not all the
            same kind of game.
          </p>
        {/if}

        <section aria-labelledby="because">
          <h3 id="because">Because you love</h3>
          <ul class="bars">
            {#each e.attributions as a (a.game)}
              {@const share = absTotal > 0 ? Math.abs(a.total) / absTotal : 0}
              {@const easeShare = a.total !== 0 ? Math.min(1, Math.max(0, a.ease / a.total)) : 0}
              <li>
                <span class="who">{games[a.game].title}</span>
                <span class="val" class:neg={a.total < 0}>{a.total < 0 ? '−' : ''}{pct(sum !== 0 ? Math.abs(a.total) / Math.abs(sum) : 0)}</span>
                <span class="track" aria-hidden="true">
                  <span class="fill" class:neg={a.total < 0} style:width={`${share * 100}%`}>
                    <span class="ease" style:width={`${easeShare * 100}%`}></span>
                  </span>
                </span>
              </li>
            {/each}
          </ul>
          <p class="legend">
            <span class="key gold" aria-hidden="true"></span>played by the same people
            <span class="key violet" aria-hidden="true"></span>linked by tags and studios
          </p>
          <p class="exact" title="The contributions add up to the score exactly: no approximation.">
            These shares are exact: they add up to the score, {num(e.score)}.
          </p>
        </section>

        {#if said.quotes.length || said.others.length}
          <section aria-labelledby="voices">
            {#if said.quotes.length && said.bridge !== null}
              <h3 id="voices">Players who also played {games[said.bridge].title} say</h3>
              {#each said.quotes as q, k (k)}
                {@render quote(q, q.yours.filter((j) => j !== said.bridge).map((j) => games[j].title))}
              {/each}
            {/if}
            {#if said.others.length}
              <h3 id={said.quotes.length ? undefined : 'voices'} class:more={said.quotes.length > 0}>
                {said.quotes.length ? 'Other players say' : 'What players say'}
              </h3>
              {#each said.others as q, k (k)}
                {@render quote(q, [])}
              {/each}
            {/if}
          </section>
        {/if}

        {#if terms.length}
          <section aria-labelledby="terms">
            <h3 id="terms">{shared.length >= 2 ? 'Both communities talk about' : 'Players talk about'}</h3>
            <ul class="terms">
              {#each terms as w (w)}<li>{w}</li>{/each}
            </ul>
          </section>
        {/if}

        <section aria-labelledby="change">
          <h3 id="change">What would change it</h3>
          {#if wholeList}
            <p>Every game in your sky pulls toward this one. It only drops out of your ten if you remove them all.</p>
          {:else}
            <p>Without <strong>{list(removedNames)}</strong> in your sky, this game drops out of your ten.</p>
          {/if}
          <p class="small">Checked by running the whole recommender again ({e.counterfactual.runs} {e.counterfactual.runs === 1 ? 'run' : 'runs'}).</p>
        </section>

        {#if e.paths.length}
          <section aria-labelledby="related">
            <h3 id="related">How it connects to your games</h3>
            <ul class="paths">
              {#each e.paths as p, k (k)}
                <li>
                  {#if p.kind === 'co-play'}
                    Often played together with <strong>{games[p.source].title}</strong>.
                  {:else if p.kind === 'tag'}
                    Shares the tag <strong>{hubName(p.via)}</strong> with {games[p.source].title}.
                  {:else if p.kind === 'developer'}
                    Made by <strong>{hubName(p.via)}</strong>, like {games[p.source].title}.
                  {:else}
                    Published by <strong>{hubName(p.via)}</strong>, like {games[p.source].title}.
                  {/if}
                </li>
              {/each}
            </ul>
          </section>
        {/if}
      </div>
    {/key}
  </section>
{/if}

<style>
  .detail {
    padding: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    max-height: 100%;
  }
  .enter {
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--line) transparent;
    animation: reveal var(--dur-draw) var(--ease-out);
  }
  @keyframes reveal {
    from {
      opacity: 0;
      transform: translateY(10px);
      filter: blur(3px);
    }
    to {
      opacity: 1;
      transform: none;
      filter: none;
    }
  }
  .art {
    position: relative;
    margin: 0;
    aspect-ratio: 460 / 215;
    background: var(--midnight);
  }
  .art img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .art::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, transparent 55%, var(--deep) 100%);
    pointer-events: none;
  }
  .plate {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    padding: var(--space-5);
    text-align: center;
    background:
      radial-gradient(circle at 30% 30%, rgb(142 107 240 / 0.45), transparent 60%),
      radial-gradient(circle at 75% 70%, rgb(242 193 78 / 0.25), transparent 55%),
      var(--midnight);
    font-size: var(--text-xl);
    color: var(--gold-bright);
  }
  .tier-pill {
    position: absolute;
    left: var(--space-4);
    bottom: var(--space-3);
    z-index: 1;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 4px 12px 4px 10px;
    border-radius: var(--radius-pill);
    background: rgb(7 11 30 / 0.85);
    border: 1px solid color-mix(in srgb, var(--tier) 60%, transparent);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text);
  }
  .tier-pill .dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--tier);
    box-shadow: 0 0 12px var(--tier);
  }
  header,
  .closeness,
  .variety,
  .enter > section {
    padding: 0 var(--space-5);
  }
  header {
    padding-top: var(--space-3);
  }
  .rank {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--gold);
    font-weight: 600;
  }
  h2 {
    font-size: var(--text-2xl);
    margin: 2px 0 var(--space-2);
  }
  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: 4px var(--space-4);
    margin: 0 0 var(--space-3);
    color: var(--muted);
    font-size: var(--text-sm);
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  .steam {
    text-decoration: none;
  }
  .steam:hover {
    color: var(--on-pick);
  }
  .closeness {
    margin-top: var(--space-4);
  }
  .scale {
    position: relative;
    height: 6px;
    border-radius: var(--radius-pill);
  }
  .marker {
    position: absolute;
    top: 50%;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 2px solid var(--starlight);
    background: var(--midnight);
    transform: translate(-50%, -50%);
    box-shadow: 0 0 14px rgb(255 255 255 / 0.6);
  }
  .closeness p {
    margin: var(--space-2) 0 0;
    font-size: var(--text-sm);
    color: var(--muted);
  }
  .closeness strong {
    color: var(--text);
  }
  .variety {
    margin: var(--space-3) var(--space-5) 0;
    padding: var(--space-2) var(--space-3);
    border-left: 2px solid var(--violet);
    background: color-mix(in srgb, var(--violet) 10%, transparent);
    border-radius: 0 8px 8px 0;
    font-size: var(--text-sm);
  }
  .enter > section {
    margin-top: var(--space-5);
  }
  .enter > section:last-child {
    padding-bottom: var(--space-5);
  }
  h3 {
    margin-bottom: var(--space-2);
  }
  h3.more {
    margin-top: var(--space-4);
  }
  .bars {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .bars li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 4px var(--space-3);
  }
  .who {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .val {
    font-weight: 600;
    color: var(--gold);
  }
  .val.neg {
    color: var(--bad);
  }
  .track {
    grid-column: 1 / -1;
    height: 6px;
    border-radius: var(--radius-pill);
    background: color-mix(in srgb, var(--midnight) 70%, transparent);
    overflow: hidden;
  }
  .fill {
    display: block;
    height: 100%;
    background: var(--violet);
    border-radius: var(--radius-pill);
    transform-origin: left;
    animation: grow var(--dur-draw) var(--ease-out);
  }
  .fill.neg {
    background: var(--bad);
  }
  .fill .ease {
    display: block;
    height: 100%;
    background: var(--gold);
  }
  @keyframes grow {
    from {
      transform: scaleX(0);
    }
  }
  .legend {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    margin: var(--space-3) 0 0;
    font-size: var(--text-xs);
    color: var(--muted);
  }
  .key {
    width: 10px;
    height: 10px;
    border-radius: 3px;
  }
  .key.violet {
    margin-left: var(--space-3);
    background: var(--violet);
  }
  .key.gold {
    background: var(--gold);
  }
  .exact,
  .small {
    margin: var(--space-2) 0 0;
    font-size: var(--text-xs);
    color: var(--muted);
  }
  .quote {
    margin: 0 0 var(--space-3);
    padding: var(--space-3) var(--space-4);
    background: color-mix(in srgb, var(--midnight) 55%, transparent);
    border-radius: 12px;
    border-left: 2px solid var(--gold);
  }
  blockquote {
    margin: 0;
    font-family: var(--font-display);
    font-style: italic;
    font-size: 17px;
    line-height: 1.45;
  }
  blockquote::before {
    content: '“';
  }
  blockquote::after {
    content: '”';
  }
  .quote figcaption {
    margin-top: var(--space-2);
    font-size: var(--text-xs);
    color: var(--muted);
  }
  .terms {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .terms li {
    padding: 3px 11px;
    border-radius: var(--radius-pill);
    border: 1px solid color-mix(in srgb, var(--violet) 50%, transparent);
    color: var(--link);
    font-size: var(--text-sm);
  }
  section p {
    margin: 0;
  }
  .paths {
    margin: 0;
    padding-left: 1.1em;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
</style>
