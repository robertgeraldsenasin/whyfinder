<script lang="ts">
  import { pct, rank } from '../format';
  import { app } from '../state.svelte';

  const result = $derived(app.result);
  const games = $derived(app.slice?.games ?? []);

  function topReason(t: number): string {
    const e = result?.explanations[t];
    if (!e || e.score <= 0) return '';
    const top = e.attributions[0];
    return `${games[top.game].title} ${pct(top.total / e.score)}`;
  }

  function onKey(e: KeyboardEvent): void {
    if (!result) return;
    const n = result.picks.length;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') app.selected = (app.selected + 1) % n;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') app.selected = (app.selected - 1 + n) % n;
    else return;
    e.preventDefault();
    document.getElementById(`pick-${app.selected}`)?.focus();
  }
</script>

{#if result}
  <section class="rail" aria-label="Your picks">
    <h2 class="sr-only">Picks</h2>
    <ol>
      {#each result.picks as p, t (p)}
        <li style:animation-delay={app.reducedMotion ? '0ms' : `${t * 40}ms`}>
          <button
            id={`pick-${t}`}
            class="card"
            class:selected={app.selected === t}
            aria-pressed={app.selected === t}
            tabindex={app.selected === t ? 0 : -1}
            onclick={() => (app.selected = t)}
            onkeydown={onKey}
          >
            <span class="rank mono">{rank(t)}</span>
            <span class="body">
              <span class="name">{games[p].title}</span>
              {#if result.variety[t]}
                <span class="chip link">Kept for variety</span>
              {:else}
                <span class="reason micro">{topReason(t)}</span>
              {/if}
            </span>
          </button>
        </li>
      {/each}
    </ol>
  </section>
{/if}

<style>
  .rail {
    min-width: 0;
  }
  ol {
    list-style: none;
    margin: 0;
    padding: 2px 2px 6px;
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 8px;
  }
  li {
    animation: rise 220ms var(--ease-out) both;
    min-width: 0;
  }
  .card {
    width: 100%;
    height: 100%;
    display: flex;
    gap: 10px;
    align-items: flex-start;
    text-align: left;
    padding: 10px 12px;
    background: var(--surface);
    border: var(--border);
    border-radius: var(--radius);
    color: var(--text);
    cursor: pointer;
    transition:
      border-color var(--dur-fast),
      background var(--dur-fast),
      transform var(--dur-fast);
  }
  .card:hover {
    background: var(--raised);
  }
  .card.selected {
    border-color: var(--pick);
    background: var(--raised);
  }
  .rank {
    font-size: var(--text-xs);
    color: var(--pick);
    padding-top: 2px;
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }
  .name {
    font-size: var(--text-sm);
    font-weight: 600;
    line-height: 1.3;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
  }
  .reason {
    font-size: 10px;
    letter-spacing: 0.04em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .chip {
    font-size: 9px;
    padding: 1px 6px;
    align-self: flex-start;
  }
  @media (max-width: 1180px) {
    ol {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>
