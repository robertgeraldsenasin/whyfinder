<script lang="ts">
  import { int, price } from '../format';
  import { app } from '../state.svelte';

  const g = $derived(app.inspect !== null ? app.slice?.games[app.inspect] : null);
  const owned = $derived(app.inspect !== null && app.history.some((h) => h.index === app.inspect));
</script>

{#if g && app.inspect !== null}
  <div class="anchor" data-anchor-game={app.inspect}>
    <div class="panel card" role="dialog" aria-label={`About ${g.title}`}>
      <button class="close" aria-label="Close" onclick={() => (app.inspect = null)}>×</button>
      <p class="title">{g.title}</p>
      <p class="micro">{g.year ?? 'year n/a'} · {price(g.price)} · {int(g.plays)} train reviews</p>
      {#if g.developer}<p class="dev">{g.developer}</p>{/if}
      <p class="tags">{g.tags.slice(0, 5).join(' · ')}</p>
      <button
        class="btn primary"
        disabled={owned || app.history.length >= 12}
        onclick={() => {
          app.add(app.inspect!);
          app.inspect = null;
        }}>{owned ? 'In your games' : '+ Add to your games'}</button
      >
    </div>
  </div>
{/if}

<style>
  .anchor {
    position: fixed;
    left: 0;
    top: 0;
    z-index: 25;
    pointer-events: none;
  }
  .card {
    pointer-events: auto;
    width: 260px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: var(--space-3) var(--space-4);
    animation: rise var(--dur-fast) var(--ease-out);
  }
  .title {
    margin: 0;
    font-family: var(--font-display);
    font-weight: 600;
    font-size: var(--text-lg);
    padding-right: 20px;
  }
  .micro,
  .dev,
  .tags {
    margin: 0;
  }
  .dev,
  .tags {
    font-size: var(--text-sm);
    color: var(--muted);
  }
  .close {
    position: absolute;
    top: 6px;
    right: 8px;
    border: 0;
    background: transparent;
    color: var(--muted);
    font-size: 18px;
    cursor: pointer;
  }
  .btn {
    margin-top: 4px;
    justify-content: center;
  }
</style>
