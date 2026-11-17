<script lang="ts">
  import * as sfx from '../sfx';
  import { app } from '../state.svelte';
  import GameSearch from './GameSearch.svelte';

  const games = $derived(app.slice?.games ?? []);
  const label = $derived(
    app.running ? 'Reading the sky' : app.result && !app.stale ? 'Your picks are up to date' : app.result ? 'Update my picks' : 'Find my next game',
  );

  function find(): void {
    sfx.unlock();
    void app.find();
  }
</script>

<section class="panel tray" aria-labelledby="your-sky">
  <div class="head">
    <h2 id="your-sky">Your sky</h2>
    <span class="count">{app.history.length} of 12</span>
  </div>
  <GameSearch />
  {#if app.history.length}
    <ul class="mine" aria-label="Your games and hours played">
      {#each app.history as h (h.index)}
        <li>
          <span class="star" aria-hidden="true"></span>
          <span class="title">{games[h.index]?.title}</span>
          <label class="hours">
            <span class="sr-only">Hours played in {games[h.index]?.title}</span>
            <input
              type="number"
              min="0"
              max="5000"
              step="1"
              value={h.hours}
              onchange={(e) => app.setHours(h.index, Math.max(0, Number((e.currentTarget as HTMLInputElement).value) || 0))}
            />
            <span aria-hidden="true">h</span>
          </label>
          <button class="remove" aria-label={`Remove ${games[h.index]?.title}`} onclick={() => app.remove(h.index)}>
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4 L12 12 M12 4 L4 12" /></svg>
          </button>
        </li>
      {/each}
    </ul>
    <button class="btn primary find" disabled={app.running || !app.ready || (!!app.result && !app.stale)} onclick={find}>
      {label}
    </button>
    <p class="note">Hours tell the engine how much each game counts. You can also click any star to add it.</p>
  {/if}
</section>

<style>
  .tray {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
  }
  h2 {
    font-size: var(--text-xl);
  }
  .count {
    font-size: var(--text-xs);
    color: var(--muted);
  }
  .mine {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .mine li {
    display: grid;
    grid-template-columns: 14px minmax(0, 1fr) auto auto;
    align-items: center;
    gap: var(--space-2);
    padding: 6px 4px 6px 6px;
    border-radius: 10px;
    animation: rise var(--dur-mid) var(--ease-out);
  }
  .mine li:hover {
    background: color-mix(in srgb, var(--raised) 60%, transparent);
  }
  .star {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--starlight);
    box-shadow:
      0 0 6px 1px rgb(255 255 255 / 0.7),
      0 0 14px 2px rgb(255 227 154 / 0.35);
  }
  .title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .hours {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    color: var(--muted);
    font-size: var(--text-sm);
  }
  .hours input {
    width: 58px;
    text-align: right;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    background: color-mix(in srgb, var(--midnight) 60%, transparent);
    color: var(--text);
    padding: 3px 6px;
  }
  .hours input:hover,
  .hours input:focus {
    border-color: var(--line);
  }
  .remove {
    width: 28px;
    height: 28px;
    display: grid;
    place-items: center;
    border: 0;
    border-radius: 50%;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
  }
  .remove svg {
    width: 12px;
    height: 12px;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
  }
  .remove:hover {
    color: var(--text);
    background: var(--raised);
  }
  .find {
    padding: 12px 18px;
    font-size: var(--text-md);
  }
  .note {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--muted);
  }
</style>
