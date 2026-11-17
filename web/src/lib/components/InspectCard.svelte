<script lang="ts">
  import { int, price, studio } from '../format';
  import * as sfx from '../sfx';
  import { app } from '../state.svelte';

  const g = $derived(app.inspect !== null ? app.slice?.games[app.inspect] : null);
  const owned = $derived(app.inspect !== null && app.history.some((h) => h.index === app.inspect));
</script>

{#if g && app.inspect !== null}
  <div class="anchor" data-anchor-game={app.inspect}>
    <div class="panel card" role="dialog" aria-label={`About ${g.title}`}>
      <button class="close" aria-label="Close" onclick={() => (app.inspect = null)}>
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4 L12 12 M12 4 L4 12" /></svg>
      </button>
      <p class="title display">{g.title}</p>
      {#if g.developer}<p class="dev">{studio(g.developer)}{g.year ? `, ${g.year}` : ''}</p>{/if}
      <p class="facts">{price(g.price)}. Reviewed by {int(g.plays)} players in the training data.</p>
      {#if g.tags.length}<p class="tags">{g.tags.slice(0, 5).join(', ')}</p>{/if}
      <button
        class="btn primary"
        disabled={owned || app.history.length >= 12}
        onclick={() => {
          app.add(app.inspect!);
          sfx.twinkle();
          app.inspect = null;
        }}>{owned ? 'Already in your sky' : 'Add to your sky'}</button
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
    font-weight: 400;
    font-size: 22px;
    padding-right: 20px;
  }
  .facts,
  .dev,
  .tags {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--muted);
  }
  .dev {
    color: var(--text);
  }
  .close {
    position: absolute;
    top: 8px;
    right: 8px;
    width: 28px;
    height: 28px;
    display: grid;
    place-items: center;
    border: 0;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
  }
  .close:hover {
    background: var(--raised);
    color: var(--text);
  }
  .close svg {
    width: 12px;
    height: 12px;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
  }
  .btn {
    margin-top: 4px;
    justify-content: center;
  }
</style>
