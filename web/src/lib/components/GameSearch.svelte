<script lang="ts">
  import * as sfx from '../sfx';
  import { app } from '../state.svelte';

  let { size = 'compact' }: { size?: 'hero' | 'compact' } = $props();

  let query = $state('');
  let active = $state(0);
  let open = $state(false);
  let input: HTMLInputElement;
  const listId = $derived(`game-options-${size}`);

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
    return hits
      .sort((a, b) => a[1] - b[1])
      .slice(0, 8)
      .map(([i]) => i);
  });
  const full = $derived(app.history.length >= 12);

  function choose(i: number): void {
    sfx.unlock();
    app.add(i);
    sfx.twinkle();
    query = '';
    open = false;
    active = 0;
    requestAnimationFrame(() => input?.focus());
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
</script>

<div class="search {size}">
  <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 2.5 L13.9 10.1 L21.5 12 L13.9 13.9 L12 21.5 L10.1 13.9 L2.5 12 L10.1 10.1 Z" />
  </svg>
  <input
    bind:this={input}
    type="text"
    role="combobox"
    aria-expanded={open && matches.length > 0}
    aria-controls={listId}
    aria-autocomplete="list"
    aria-activedescendant={open && matches.length ? `${listId}-${matches[active]}` : undefined}
    aria-label="Add a game you like"
    placeholder={full ? 'Your sky is full: twelve games' : app.history.length ? 'Add another game you love' : 'Search 500 Steam games'}
    disabled={full}
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
          id={`${listId}-${i}`}
          role="option"
          aria-selected={k === active}
          class:active={k === active}
          onmousedown={(e) => {
            e.preventDefault();
            choose(i);
          }}
        >
          <span class="t">{games[i].title}</span>
          <span class="y">{games[i].year ?? ''}</span>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .search {
    position: relative;
  }
  .icon {
    position: absolute;
    left: 16px;
    top: 50%;
    width: 16px;
    height: 16px;
    transform: translateY(-50%);
    fill: var(--gold);
    pointer-events: none;
  }
  input {
    width: 100%;
    border: 1px solid var(--line);
    border-bottom-color: var(--frame-line);
    background: color-mix(in srgb, var(--midnight) 70%, var(--deep));
    color: var(--text);
    border-radius: 0;
    padding: 12px 16px 10px 42px;
    outline: none;
    transition:
      border-color var(--dur-fast) var(--ease-out),
      box-shadow var(--dur-fast) var(--ease-out);
  }
  input::placeholder {
    color: var(--muted);
  }
  input:focus {
    border-color: var(--gold);
    box-shadow: 0 0 40px -12px rgb(242 193 78 / 0.55);
  }
  input:disabled {
    opacity: 0.6;
  }
  .hero input {
    font-size: var(--text-lg);
    padding: 19px 24px 16px 56px;
    background: color-mix(in srgb, var(--midnight) 60%, transparent);
    border-color: var(--frame-line);
    border-bottom: 2px solid var(--gold);
    box-shadow: 0 24px 60px -34px rgb(242 193 78 / 0.6);
  }
  .hero .icon {
    left: 22px;
    width: 20px;
    height: 20px;
  }
  ul {
    position: absolute;
    z-index: 20;
    left: 0;
    right: 0;
    top: calc(100% + 6px);
    margin: 0;
    padding: 6px;
    list-style: none;
    background: var(--surface-solid);
    border: 1px solid var(--frame-line);
    box-shadow: 0 24px 60px -20px rgb(0 0 0 / 0.9);
    animation: rise var(--dur-fast) var(--ease-out);
  }
  li {
    display: flex;
    justify-content: space-between;
    gap: var(--space-3);
    padding: 10px 12px 8px;
    cursor: pointer;
  }
  li.active {
    background: var(--raised);
    box-shadow: inset 2px 0 0 var(--gold);
  }
  .hero li {
    padding: 11px 16px;
    font-size: var(--text-lg);
  }
  .y {
    color: var(--muted);
    font-size: var(--text-sm);
  }
</style>
