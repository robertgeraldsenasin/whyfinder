<script lang="ts">
  import * as sfx from '../sfx';
  import { settings } from '../settings.svelte';
  import { colorAt, tier } from '../sky';
  import { app } from '../state.svelte';

  let { closeness }: { closeness: Float32Array | null } = $props();

  const result = $derived(app.result);
  const games = $derived(app.slice?.games ?? []);
  const n = $derived(result?.picks.length ?? 0);
  const firstVisible = $derived(n - app.landed);

  function choose(t: number): void {
    app.selected = t;
    sfx.select();
  }

  function onKey(e: KeyboardEvent): void {
    if (!result) return;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') app.selected = (app.selected + 1) % n;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') app.selected = (app.selected - 1 + n) % n;
    else return;
    e.preventDefault();
    sfx.select();
    document.getElementById(`pick-${app.selected}`)?.focus();
  }
</script>

{#if result}
  <section class="panel list" aria-labelledby="fell-title">
    <div class="head">
      <h2 id="fell-title">Where the stars fell</h2>
      {#if app.falling}
        <button class="btn ghost skip" onclick={() => app.skipFall++}>Skip</button>
      {/if}
    </div>
    <div role="region" aria-label="Your picks">
      <ol>
        {#each result.picks as p, t (p)}
          {@const c = closeness?.[p] ?? 0}
          {#if t >= firstVisible}
            <li class:landing={app.falling}>
              <button
                id={`pick-${t}`}
                class="row"
                class:selected={app.selected === t && !app.falling}
                aria-pressed={app.selected === t}
                tabindex={app.selected === t ? 0 : -1}
                onclick={() => choose(t)}
                onkeydown={onKey}
              >
                <span class="rank display">{t + 1}</span>
                <span class="name">{games[p].title}</span>
                <span class="tier">
                  <span class="dot" style:background={colorAt(settings.palette, c)} style:box-shadow={`0 0 10px ${colorAt(settings.palette, c)}`}></span>
                  <span>{tier(c).name}{#if result.variety[t]}<span class="variety">, picked for variety</span>{/if}</span>
                </span>
              </button>
            </li>
          {/if}
        {/each}
      </ol>
    </div>
  </section>
{/if}

<style>
  .list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding-bottom: var(--space-3);
  }
  .head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
  }
  h2 {
    font-size: var(--text-xl);
  }
  .skip {
    padding: 4px 12px;
  }
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  li.landing {
    animation: land 520ms var(--ease-out);
  }
  @keyframes land {
    0% {
      opacity: 0;
      transform: translateY(-10px) scale(0.98);
      filter: brightness(2.2);
    }
    40% {
      opacity: 1;
      filter: brightness(1.6);
    }
    100% {
      transform: none;
      filter: none;
    }
  }
  .row {
    width: 100%;
    display: grid;
    grid-template-columns: 30px minmax(0, 1fr);
    grid-template-areas:
      'rank name'
      'rank tier';
    column-gap: var(--space-2);
    align-items: center;
    text-align: left;
    background: transparent;
    border: 0;
    border-left: 2px solid transparent;
    border-bottom: 1px solid color-mix(in srgb, var(--line) 60%, transparent);
    padding: 9px 10px 7px 6px;
    cursor: pointer;
    transition:
      background var(--dur-fast) var(--ease-out),
      border-color var(--dur-fast) var(--ease-out);
  }
  .row:hover {
    background: color-mix(in srgb, var(--raised) 70%, transparent);
  }
  .row.selected {
    background: linear-gradient(90deg, color-mix(in srgb, var(--gold) 16%, var(--raised)), var(--raised) 60%);
    border-left-color: var(--gold);
  }
  .rank {
    grid-area: rank;
    font-size: 26px;
    line-height: 1;
    text-align: center;
    color: var(--gold);
  }
  .name {
    grid-area: name;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .tier {
    grid-area: tier;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-size: var(--text-xs);
    color: var(--muted);
  }
  .dot {
    width: 7px;
    height: 7px;
    transform: rotate(45deg);
    flex: none;
  }
  .variety {
    color: var(--link);
  }
</style>
