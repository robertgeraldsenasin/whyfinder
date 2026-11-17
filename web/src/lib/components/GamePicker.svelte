<script lang="ts">
  import { app } from '../state.svelte';

  let query = $state('');
  let active = $state(0);
  let open = $state(false);
  const listId = 'game-options';

  const games = $derived(app.slice?.games ?? []);
  const owned = $derived(new Set(app.history.map((h) => h.index)));
  const matches = $derived.by(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [] as number[];
    const hits: [number, number][] = [];
    games.forEach((g, i) => {
      if (owned.has(i)) return;
      const t = g.title.toLowerCase();
      const at = t.indexOf(q);
      if (at >= 0) hits.push([i, (at === 0 ? 0 : 1) * 1e7 - g.plays]);
    });
    return hits.sort((a, b) => a[1] - b[1]).slice(0, 8).map(([i]) => i);
  });

  const PRESETS: [string, string[], number[]][] = [
    ['Puzzles & stories', ['Portal 2', 'Undertale', 'The Stanley Parable'], [40, 12, 3]],
    ['Survival crews', ['Rust', 'DayZ', 'Arma 3'], [300, 120, 80]],
    ['Roguelike runs', ['FTL: Faster Than Light', 'The Binding of Isaac', 'XCOM: Enemy Unknown'], [60, 90, 45]],
    ['Grand strategy', ["Sid Meier's Civilization® V", 'Stellaris', 'Mount & Blade: Warband'], [400, 60, 90]],
  ];
  const presets = $derived(
    PRESETS.map(([name, titles, hours]) => ({
      name,
      items: titles
        .map((t, k) => ({ index: games.findIndex((g) => g.title === t), hours: hours[k] }))
        .filter((x) => x.index >= 0),
    })).filter((p) => p.items.length >= 2),
  );

  function choose(i: number): void {
    app.add(i);
    query = '';
    open = false;
    active = 0;
  }

  function onKey(e: KeyboardEvent): void {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      open = true;
      active = Math.min(active + 1, matches.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      active = Math.max(active - 1, 0);
    } else if (e.key === 'Enter' && matches.length) {
      e.preventDefault();
      choose(matches[active]);
    } else if (e.key === 'Escape') {
      open = false;
    }
  }

  function usePreset(items: { index: number; hours: number }[]): void {
    app.history = items.map((x) => ({ ...x }));
    void app.find();
  }
</script>

<section class="panel picker" aria-labelledby="your-games">
  <h2 id="your-games" class="micro">Your games</h2>

  <div class="search">
    <span class="spark" aria-hidden="true">✦</span>
    <input
      type="text"
      role="combobox"
      aria-expanded={open && matches.length > 0}
      aria-controls={listId}
      aria-autocomplete="list"
      aria-activedescendant={open && matches.length ? `opt-${matches[active]}` : undefined}
      aria-label="Add a game you like"
      placeholder={app.history.length ? 'Add another game…' : 'Add a game you love…'}
      bind:value={query}
      oninput={() => {
        open = true;
        active = 0;
      }}
      onkeydown={onKey}
      onblur={() => setTimeout(() => (open = false), 120)}
    />
    {#if open && matches.length}
      <ul id={listId} role="listbox" aria-label="Matching games">
        {#each matches as i, k (i)}
          <li
            id={`opt-${i}`}
            role="option"
            aria-selected={k === active}
            class:active={k === active}
            onmousedown={(e) => {
              e.preventDefault();
              choose(i);
            }}
          >
            <span>{games[i].title}</span>
            <span class="micro">{games[i].year ?? ''}</span>
          </li>
        {/each}
      </ul>
    {/if}
  </div>

  {#if app.history.length}
    <ul class="chips" aria-label="Your games and hours played">
      {#each app.history as h (h.index)}
        <li>
          <span class="dot" aria-hidden="true"></span>
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
          <button class="remove" aria-label={`Remove ${games[h.index]?.title}`} onclick={() => app.remove(h.index)}>×</button>
        </li>
      {/each}
    </ul>
    <button class="btn primary find" disabled={app.running || !app.ready} onclick={() => app.find()}>
      {app.running ? 'Finding…' : app.result && !app.stale ? 'Picks are up to date' : app.result ? 'Update picks' : 'Find my picks'}
    </button>
    <p class="note">Hours set each game's weight: x = 1 + ln(1 + hours). Click any star on the map to inspect or add it.</p>
  {:else}
    <p class="lead">Pick a few games you love. The engine runs in your browser and shows exactly why it picks each game.</p>
    <p class="micro">Or start from a constellation</p>
    <div class="presets">
      {#each presets as p (p.name)}
        <button class="btn preset" disabled={!app.ready} onclick={() => usePreset(p.items)}>
          <span class="pname">{p.name}</span>
          <span class="micro">{p.items.map((x) => games[x.index].title).join(' · ')}</span>
        </button>
      {/each}
    </div>
  {/if}
</section>

<style>
  .picker {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    max-height: 100%;
  }
  h2 {
    margin: 0;
  }
  .search {
    position: relative;
  }
  .spark {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--pick);
  }
  input[type='text'] {
    width: 100%;
    padding: 10px 12px 10px 34px;
    border-radius: 8px;
    border: var(--border);
    background: var(--bg);
    color: var(--text);
  }
  input::placeholder {
    color: var(--muted);
  }
  [role='listbox'] {
    position: absolute;
    z-index: 20;
    left: 0;
    right: 0;
    top: calc(100% + 4px);
    margin: 0;
    padding: 4px;
    list-style: none;
    background: var(--surface);
    border: var(--border);
    border-radius: 8px;
    box-shadow: 0 16px 40px -20px rgb(0 0 0 / 0.6);
  }
  [role='option'] {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    padding: 7px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-size: var(--text-sm);
  }
  [role='option'].active,
  [role='option']:hover {
    background: var(--raised);
  }
  .chips {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .chips li {
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--raised);
    border-radius: var(--radius-pill);
    padding: 4px 6px 4px 12px;
    animation: rise var(--dur-fast) var(--ease-out);
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--star);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--star) 20%, transparent);
    flex: none;
  }
  .title {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--text-sm);
  }
  .hours {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--muted);
  }
  .hours input {
    width: 52px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    text-align: right;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text);
    padding: 2px 4px;
  }
  .hours input:hover,
  .hours input:focus {
    border-color: var(--line);
  }
  .remove {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    border: 0;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    font-size: 16px;
  }
  .remove:hover {
    color: var(--text);
    background: var(--surface);
  }
  .find {
    justify-content: center;
  }
  .note,
  .lead {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--muted);
  }
  .lead {
    color: var(--text);
  }
  .presets {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .preset {
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    text-align: left;
    background: var(--bg);
  }
  .preset .micro {
    font-size: 10px;
    text-transform: none;
    letter-spacing: 0.02em;
  }
  .pname {
    font-weight: 600;
    font-size: var(--text-sm);
  }
</style>
