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
  <span class="stub" aria-hidden="true">
    <svg class="icon" viewBox="0 0 24 24"><path d="M12 1l2.3 8.7L23 12l-8.7 2.3L12 23l-2.3-8.7L1 12l8.7-2.3z" /></svg>
  </span>
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
  {#if size === 'hero'}<span class="admit" aria-hidden="true">Admit one</span>{/if}
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
  /* Inputs that matter are printed on bone. The hero search is an admission ticket: a stub with a
     perforation, the field, and "Admit one" along the edge, with a crimson offset. */
  .search {
    position: relative;
    display: flex;
    align-items: stretch;
    background: var(--bone);
    color: var(--on-bone);
    box-shadow: 4px 4px 0 var(--crimson);
    transition: box-shadow var(--dur-fast) var(--ease-out);
  }
  .search:focus-within {
    box-shadow:
      4px 4px 0 var(--crimson),
      0 0 0 2px var(--crimson);
  }
  .stub {
    flex: none;
    display: grid;
    place-items: center;
    width: 40px;
  }
  .icon {
    width: 15px;
    height: 15px;
    fill: var(--crimson);
  }
  input {
    flex: 1;
    min-width: 0;
    border: 0;
    background: transparent;
    color: var(--on-bone);
    border-radius: 0;
    padding: 11px 12px 9px 0;
    outline: none;
  }
  input::placeholder {
    color: var(--on-bone-muted);
  }
  input:disabled {
    opacity: 0.7;
  }
  .hero {
    box-shadow: 7px 7px 0 var(--crimson);
    text-align: left;
  }
  .hero:focus-within {
    box-shadow:
      7px 7px 0 var(--crimson),
      0 0 0 3px var(--crimson);
  }
  .hero .stub {
    width: 74px;
    border-right: 2px dashed rgb(26 14 24 / 0.35);
  }
  .hero .icon {
    width: 26px;
    height: 26px;
  }
  .hero input {
    font-size: 21px;
    padding: 21px 22px 17px;
  }
  .admit {
    flex: none;
    align-self: center;
    margin-right: 16px;
    font-family: var(--font-poster);
    font-size: 13px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--crimson);
    writing-mode: vertical-rl;
    transform: rotate(180deg);
  }
  ul {
    position: absolute;
    z-index: 20;
    left: 0;
    right: 0;
    top: calc(100% + 10px);
    margin: 0;
    padding: 6px;
    list-style: none;
    background: var(--surface-solid);
    border: var(--border);
    box-shadow:
      5px 5px 0 var(--crimson),
      0 24px 60px -20px rgb(0 0 0 / 0.9);
    color: var(--text);
    text-align: left;
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
    box-shadow: inset 3px 0 0 var(--crimson);
  }
  .hero li {
    padding: 11px 16px;
    font-size: var(--text-lg);
  }
  .y {
    color: var(--muted);
    font-size: var(--text-sm);
  }
  @media (max-width: 520px) {
    .hero .stub {
      width: 52px;
    }
    .hero input {
      font-size: 17px;
      padding: 16px 12px 13px;
    }
  }
</style>
