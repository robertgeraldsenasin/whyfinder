<script lang="ts">
  import { PIPS, rankLabel, rankName, split, SUITS, suitOf } from '../cards';
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
  const suit = $derived(e ? suitOf(e.attributions) : 'hearts');
  const parts = $derived(e ? split(e.attributions) : { ease: 0, ppr: 0 });
  /** Share of the score's magnitude carried by the part that names the suit. */
  const carried = $derived.by(() => {
    const whole = Math.abs(parts.ease) + Math.abs(parts.ppr);
    return whole > 0 ? Math.max(parts.ease, parts.ppr) / whole : 0;
  });
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
  <figure class="voice">
    <blockquote class="balloon">{q.text}</blockquote>
    <figcaption>
      {Math.round(q.hours).toLocaleString('en-US')} hours on record{#if q.year}, reviewed in {q.year}{/if}{#if others.length}. Also
        played {list(others)}{/if}.
    </figcaption>
  </figure>
{/snippet}

{#snippet index(where: string)}
  <span class="idx {where}" aria-hidden="true">
    <span>{rankLabel(e!.rank)}</span>
    <svg viewBox="0 0 24 24"><path d={PIPS[suit]} /></svg>
  </span>
{/snippet}

{#if e && game && result}
  <section class="panel detail" aria-labelledby="pick-title">
    <p class="sr-only" aria-live="polite">Pick {e.rank + 1}, the {rankName(e.rank)} of {SUITS[suit].name.toLowerCase()}: {game.title}</p>
    {#key e.pick}
      <div class="enter">
        <div class="face on-bone {suit}">
          {@render index('tl')}
          {@render index('br')}
          <div class="pic">
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
              <div class="plate" aria-hidden="true"><span>{game.title}</span></div>
            {/if}
          </figure>
          <p class="stamp" style:--tier={colorAt(settings.palette, c)}>{t.name}</p>
          </div>
          <p class="rank">Pick {e.rank + 1} of {result.picks.length}</p>
          <h2 id="pick-title" class="display">{game.title}</h2>
          <p class="facts">
            {#if game.developer}<span>{studio(game.developer)}</span>{/if}
            {#if game.year}<span>{game.year}</span>{/if}
            <span>{price(game.price)}</span>
          </p>
        </div>

        <div class="inner">
          <div class="actions">
            <a class="btn primary steam" href={`https://store.steampowered.com/app/${game.id}`} target="_blank" rel="noreferrer">
              View on Steam
            </a>
            <button class="btn ghost" onclick={() => ((app.stage = 6), app.go('hood'))}>How this was worked out</button>
          </div>

          <div class="closeness">
            <div class="scale" style:background={gradient(settings.palette)} aria-hidden="true">
              <svg class="marker" style:left={`${c * 100}%`} viewBox="0 0 24 24"><path d={PIPS.star} /></svg>
            </div>
            <p><strong>{t.name}</strong>: {t.plain}.</p>
            <p class="suit-line {suit}">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d={PIPS[suit]} /></svg>
              <span
                ><strong>{SUITS[suit].name}</strong>: {suit === 'hearts' ? 'players in common' : 'tags and studios'} carried this pick, {pct(
                  carried,
                )} of the score.</span
              >
            </p>
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
              <span class="key crimson" aria-hidden="true"></span>played by the same people
              <span class="key quantum" aria-hidden="true"></span>linked by tags and studios
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
            <div class="twist">
              {#if wholeList}
                <p>Every game in your sky pulls toward this one. It only drops out of your ten if you remove them all.</p>
              {:else}
                <p>Without <strong>{list(removedNames)}</strong> in your sky, this game drops out of your ten.</p>
              {/if}
              <p class="small">
                Checked by running the whole recommender again ({e.counterfactual.runs} {e.counterfactual.runs === 1 ? 'run' : 'runs'}).
              </p>
            </div>
          </section>

          {#if e.paths.length}
            <section aria-labelledby="related">
              <h3 id="related">How it connects to your games</h3>
              <ul class="paths">
                {#each e.paths as p, k (k)}
                  <li>
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d={PIPS.star} /></svg>
                    <span>
                      {#if p.kind === 'co-play'}
                        Often played together with <strong>{games[p.source].title}</strong>.
                      {:else if p.kind === 'tag'}
                        Shares the tag <strong>{hubName(p.via)}</strong> with {games[p.source].title}.
                      {:else if p.kind === 'developer'}
                        Made by <strong>{hubName(p.via)}</strong>, like {games[p.source].title}.
                      {:else}
                        Published by <strong>{hubName(p.via)}</strong>, like {games[p.source].title}.
                      {/if}
                    </span>
                  </li>
                {/each}
              </ul>
            </section>
          {/if}
        </div>
      </div>
    {/key}
  </section>
{/if}

<style>
  .detail {
    padding: 0;
    display: flex;
    flex-direction: column;
    max-height: 100%;
    min-height: 0;
  }
  .enter {
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--line) transparent;
  }

  /* The card face: bone, corner indices, an inner rule, the art as its picture, a hard crimson
     shadow. It is dealt in when the pick changes. */
  .face {
    position: relative;
    margin: 18px 18px 6px;
    padding: 12px 12px 20px 52px;
    border-radius: var(--card-radius);
    box-shadow: 8px 8px 0 var(--crimson);
    animation: flip 620ms var(--ease-pop);
    transform-origin: 50% 100%;
  }
  .face.clubs {
    box-shadow: 8px 8px 0 var(--quantum);
  }
  @keyframes flip {
    0% {
      opacity: 0;
      transform: perspective(900px) translate(30px, -20px) rotateY(-70deg) rotate(6deg);
    }
    55% {
      opacity: 1;
    }
    100% {
      transform: none;
    }
  }
  .face::before {
    content: '';
    position: absolute;
    inset: 6px;
    border: 1px solid rgb(26 14 24 / 0.25);
    border-radius: 8px;
    pointer-events: none;
  }
  .idx {
    position: absolute;
    z-index: 2;
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 30px;
    line-height: 0.9;
    color: var(--crimson);
    font-family: var(--font-poster);
    font-size: 30px;
  }
  .clubs .idx {
    color: var(--club);
  }
  .idx svg {
    width: 17px;
    height: 17px;
    margin-top: 4px;
    fill: currentColor;
  }
  .idx.tl {
    left: 12px;
    top: 14px;
  }
  .idx.br {
    right: 12px;
    bottom: 14px;
    transform: rotate(180deg);
  }
  .art {
    position: relative;
    margin: 0;
    aspect-ratio: 460 / 215;
    background: var(--ink);
    border: 1px solid var(--on-bone);
    overflow: hidden;
  }
  .art img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .plate {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    padding: var(--space-4);
    text-align: center;
    background:
      radial-gradient(circle at 30% 30%, rgb(123 77 255 / 0.5), transparent 60%),
      radial-gradient(circle at 75% 70%, rgb(209 23 58 / 0.5), transparent 55%),
      var(--ink);
    font-family: var(--font-display);
    font-size: 28px;
    line-height: 1.15;
    color: var(--bone);
  }
  .plate::after {
    content: '';
    position: absolute;
    inset: 0;
    color: var(--crimson-hot);
    opacity: 0.25;
    background-image: var(--halftone);
    background-size: 7px 7px;
    -webkit-mask: linear-gradient(135deg, transparent 40%, #000);
    mask: linear-gradient(135deg, transparent 40%, #000);
  }
  /* The closeness tier, stamped on the card over the corner of the picture. */
  .pic {
    position: relative;
  }
  .stamp {
    position: absolute;
    z-index: 3;
    right: 8px;
    bottom: -16px;
    margin: 0;
    transform: rotate(-7deg);
    padding: 6px 12px 3px;
    border: 3px solid var(--crimson);
    background: rgb(247 239 230 / 0.94);
    color: var(--crimson);
    font-family: var(--font-poster);
    font-size: 16px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    box-shadow: inset 0 -3px 0 var(--tier);
    animation: stamp 420ms 260ms var(--ease-pop) backwards;
  }
  @keyframes stamp {
    from {
      opacity: 0;
      transform: rotate(-18deg) scale(1.8);
    }
  }
  .rank {
    margin: 18px 0 0;
    font-size: var(--text-xs);
    font-weight: 700;
    color: var(--crimson);
  }
  .clubs .rank {
    color: var(--club);
  }
  h2 {
    margin: 2px 0 4px;
    font-size: 30px;
    line-height: 1.1;
    color: var(--on-bone);
  }
  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: 2px var(--space-4);
    margin: 0;
    padding-right: 34px;
    color: var(--on-bone-muted);
    font-size: var(--text-sm);
  }

  .inner {
    padding: var(--space-4) var(--space-5) var(--space-5);
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-3);
  }
  .steam:hover {
    color: var(--on-pick);
  }
  .closeness {
    margin-top: var(--space-5);
  }
  .scale {
    position: relative;
    height: 6px;
    transform: skewX(-20deg);
  }
  .marker {
    position: absolute;
    top: 50%;
    width: 20px;
    height: 20px;
    transform: translate(-50%, -50%) skewX(20deg);
    fill: var(--bone);
    stroke: var(--ink);
    stroke-width: 2;
    filter: drop-shadow(0 0 6px rgb(247 239 230 / 0.7));
  }
  .closeness p {
    margin: var(--space-2) 0 0;
    font-size: var(--text-sm);
    color: var(--muted);
  }
  .closeness strong {
    color: var(--text);
  }
  .suit-line {
    display: flex;
    gap: 8px;
    align-items: flex-start;
  }
  .suit-line svg {
    flex: none;
    width: 14px;
    height: 14px;
    margin-top: 2px;
  }
  .suit-line.hearts svg {
    fill: var(--crimson-text);
  }
  .suit-line.clubs svg {
    fill: var(--quantum-text);
  }
  .variety {
    margin: var(--space-3) 0 0;
    padding: var(--space-2) var(--space-3);
    border-left: 3px solid var(--quantum);
    background: color-mix(in srgb, var(--quantum) 12%, transparent);
    font-size: var(--text-sm);
  }
  section {
    margin-top: var(--space-5);
  }
  h3 {
    margin-bottom: var(--space-3);
  }
  h3.more {
    margin-top: var(--space-4);
  }
  section p {
    margin: 0;
  }
  .bars {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .bars li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 4px var(--space-3);
    align-items: baseline;
  }
  .who {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .val {
    font-family: var(--font-poster);
    font-size: 19px;
    line-height: 1.1;
    letter-spacing: 0.02em;
    color: var(--crimson-text);
  }
  .val.neg {
    color: var(--bad);
  }
  .track {
    grid-column: 1 / -1;
    height: 8px;
    background: var(--ink);
    overflow: hidden;
    transform: skewX(-20deg);
  }
  .fill {
    display: block;
    height: 100%;
    background: var(--quantum);
    transform-origin: left;
    animation: grow var(--dur-draw) var(--ease-out);
  }
  .fill.neg {
    background: repeating-linear-gradient(90deg, var(--bad) 0 6px, transparent 6px 9px);
  }
  .fill .ease {
    display: block;
    height: 100%;
    background: var(--crimson);
  }
  .fill.neg .ease {
    display: none;
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
    gap: 7px;
    margin: var(--space-3) 0 0 !important;
    font-size: var(--text-xs);
    color: var(--muted);
  }
  .key {
    width: 14px;
    height: 8px;
    transform: skewX(-20deg);
  }
  .key.quantum {
    margin-left: var(--space-3);
    background: var(--quantum);
  }
  .key.crimson {
    background: var(--crimson);
  }
  .exact,
  .small {
    margin: var(--space-2) 0 0 !important;
    font-size: var(--text-xs);
    color: var(--muted);
  }
  /* What players wrote, in speech balloons. */
  .voice {
    margin: 0 0 var(--space-4);
  }
  .balloon {
    position: relative;
    margin: 0;
    padding: 12px 16px 11px;
    background: var(--bone);
    color: var(--on-bone);
    border-radius: 16px 16px 16px 4px;
    font-family: var(--font-voice);
    font-size: 15.5px;
    line-height: 1.45;
    box-shadow: 4px 4px 0 var(--quantum);
  }
  .balloon::before {
    content: '“';
  }
  .balloon::after {
    content: '';
    position: absolute;
    left: 14px;
    bottom: -12px;
    width: 18px;
    height: 14px;
    background: var(--bone);
    clip-path: polygon(0 0, 100% 0, 0 100%);
  }
  .voice figcaption {
    margin: 16px 0 0 4px;
    font-size: var(--text-xs);
    color: var(--muted);
  }
  /* The words both communities use, as admission tickets. */
  .terms {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .terms li {
    padding: 6px 14px 4px;
    color: var(--link);
    font-weight: 600;
    font-size: var(--text-sm);
    background: color-mix(in srgb, var(--quantum) 14%, transparent);
    border: 1px dashed color-mix(in srgb, var(--quantum-text) 55%, transparent);
  }
  .twist {
    padding: var(--space-3) var(--space-4);
    border-left: 4px solid var(--crimson);
    background: color-mix(in srgb, var(--crimson) 10%, transparent);
  }
  .paths {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .paths li {
    display: flex;
    gap: 9px;
    align-items: flex-start;
  }
  .paths svg {
    flex: none;
    width: 10px;
    height: 10px;
    margin-top: 6px;
    fill: var(--quantum-text);
  }
  @media (max-width: 520px) {
    .face {
      margin: 14px 12px 6px;
      padding-left: 44px;
    }
    .idx {
      font-size: 24px;
      width: 24px;
    }
    h2 {
      font-size: 25px;
    }
    .inner {
      padding: var(--space-4);
    }
  }
</style>
