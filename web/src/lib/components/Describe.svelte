<script lang="ts">
  /**
   * Describe what you want (FR-18, FR-23): "like Portal 2, co-op, under $20, after 2012". Titles join
   * your sky, tags, price and years become filters shown as chips you can remove, and anything the
   * parser could not place is said out loud instead of guessed.
   */
  import { describe as words } from '../query';
  import * as sfx from '../sfx';
  import { app } from '../state.svelte';

  let { size = 'compact', deal = false }: { size?: 'hero' | 'compact'; deal?: boolean } = $props();

  let text = $state('');
  let note = $state('');
  const id = $derived(`describe-${size}`);
  const f = $derived(app.filters);
  const chips = $derived([
    ...f.tags.map((t) => ({ label: t, kind: 'tag' as const, tag: t })),
    ...(f.maxPrice !== null ? [{ label: words({ ...f, tags: [], yearMin: null, yearMax: null })[0], kind: 'price' as const, tag: undefined }] : []),
    ...(f.yearMin !== null || f.yearMax !== null
      ? [{ label: words({ ...f, tags: [], maxPrice: null }).at(-1)!, kind: 'year' as const, tag: undefined }]
      : []),
  ]);

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    if (!text.trim() || !app.ready) return;
    sfx.unlock();
    const before = app.history.length;
    const { added, filters } = app.describe(text);
    const parts = [];
    if (added) parts.push(`${added} ${added === 1 ? 'game' : 'games'} added to your sky`);
    if (filters) parts.push(`${filters} ${filters === 1 ? 'filter' : 'filters'} set`);
    note = parts.length ? `${parts.join(', ')}.` : 'Nothing in that matched a game, a tag, a price or a year.';
    if (added || filters) {
      sfx.twinkle();
      text = '';
    }
    if (deal && app.history.length > 0 && before === 0) void app.find();
  }
</script>

<div class="describe {size}">
  <form onsubmit={submit}>
    <label for={id}>{size === 'hero' ? 'Or describe it' : 'Describe what you want'}</label>
    <div class="row">
      <input
        {id}
        type="text"
        bind:value={text}
        placeholder="like Portal 2, co-op, under $20, after 2012"
        autocomplete="off"
        disabled={!app.ready}
      />
      <button class="btn" type="submit" disabled={!app.ready || !text.trim()}>Apply</button>
    </div>
  </form>
  <p class="note" aria-live="polite">
    {note}{#if app.unresolved.length}
      Not understood: {app.unresolved.map((u) => `“${u}”`).join(', ')}.{/if}
  </p>
  {#if chips.length && size === 'compact'}
    <ul class="chips" aria-label="Filters">
      {#each chips as c (c.label)}
        <li>
          <button class="chip-x" aria-label={`Remove filter ${c.label}`} onclick={() => app.removeFilter(c.kind, c.tag)}>
            {c.label}<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4 L12 12 M12 4 L4 12" /></svg>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .describe {
    display: flex;
    flex-direction: column;
    gap: 6px;
    text-align: left;
  }
  label {
    font-family: var(--font-poster);
    font-size: 14px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .row {
    display: flex;
    gap: var(--space-2);
  }
  input {
    flex: 1;
    min-width: 0;
    border: var(--border);
    border-bottom: 2px solid var(--quantum);
    background: var(--ink);
    color: var(--text);
    padding: 9px 12px 7px;
    border-radius: 0;
  }
  input::placeholder {
    color: var(--muted);
  }
  input:focus {
    outline: none;
    border-color: var(--quantum-text);
  }
  .btn {
    padding: 8px 16px 6px;
  }
  .note {
    margin: 0;
    min-height: 0;
    font-size: var(--text-xs);
    color: var(--muted);
  }
  .note:empty {
    display: none;
  }
  .chips {
    list-style: none;
    margin: 2px 0 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .chip-x {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 5px 10px 3px 12px;
    border: 1px dashed color-mix(in srgb, var(--quantum-text) 60%, transparent);
    background: color-mix(in srgb, var(--quantum) 16%, transparent);
    color: var(--link);
    font-size: var(--text-sm);
    font-weight: 600;
    cursor: pointer;
  }
  .chip-x:hover {
    border-style: solid;
  }
  .chip-x svg {
    width: 10px;
    height: 10px;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
  }
  .hero {
    width: min(620px, 100%);
    margin-top: var(--space-4);
  }
  .hero label {
    font-size: 13px;
  }
</style>
