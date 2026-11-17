<script lang="ts">
  import { onMount } from 'svelte';
  import { type Flashes, settings } from '../settings.svelte';
  import * as sfx from '../sfx';
  import { gradient, PALETTES } from '../sky';

  let { onclose }: { onclose: () => void } = $props();
  let panel: HTMLDivElement;

  const EFFECTS: { id: Flashes; name: string; description: string }[] = [
    { id: 'full', name: 'Full', description: 'Brief full-screen impact frames and shake, never more than three flashes a second.' },
    { id: 'reduced', name: 'Reduced flashing', description: 'Light bursts stay around the star; gentler shake.' },
    { id: 'off', name: 'Off', description: 'No flashes and no shake.' },
  ];

  function save(): void {
    settings.save();
  }

  onMount(() => {
    panel.querySelector<HTMLElement>('input:checked')?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onclose();
    };
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (!panel.contains(t) && !(t as HTMLElement).closest?.('[aria-controls="settings-panel"]')) onclose();
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('pointerdown', onDown);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('pointerdown', onDown);
    };
  });
</script>

<div class="panel pop" id="settings-panel" role="dialog" aria-label="Settings" bind:this={panel}>
  <fieldset>
    <legend>Star colours</legend>
    <p class="help">How close each game is to your taste, from distant to closest.</p>
    {#each PALETTES as p (p.id)}
      <label class="option">
        <input type="radio" name="palette" value={p.id} bind:group={settings.palette} onchange={save} />
        <span class="body">
          <span class="name">{p.name}</span>
          <span class="swatch" style:background={gradient(p.id)} aria-hidden="true"></span>
          <span class="desc">{p.description}</span>
        </span>
      </label>
    {/each}
  </fieldset>

  <fieldset>
    <legend>Sound</legend>
    <label class="switch">
      <input
        type="checkbox"
        bind:checked={settings.sound}
        onchange={() => {
          save();
          sfx.unlock();
          sfx.twinkle();
        }}
      />
      <span>Sound effects</span>
    </label>
    <label class="volume">
      <span>Volume</span>
      <input
        type="range"
        min="0"
        max="1"
        step="0.05"
        disabled={!settings.sound}
        bind:value={settings.volume}
        onchange={() => {
          save();
          sfx.select();
        }}
      />
    </label>
  </fieldset>

  <fieldset>
    <legend>Impact effects</legend>
    {#each EFFECTS as f (f.id)}
      <label class="option">
        <input type="radio" name="flashes" value={f.id} bind:group={settings.flashes} onchange={save} />
        <span class="body">
          <span class="name">{f.name}</span>
          <span class="desc">{f.description}</span>
        </span>
      </label>
    {/each}
    <p class="help">If your device asks for reduced motion, stars appear in place with no effects at all.</p>
  </fieldset>
</div>

<style>
  .pop {
    position: absolute;
    right: 0;
    top: calc(100% + 10px);
    z-index: 50;
    width: min(360px, calc(100vw - 24px));
    max-height: calc(100dvh - 100px);
    overflow-y: auto;
    padding: var(--space-4);
    background: var(--surface-solid);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    animation: rise var(--dur-fast) var(--ease-out);
  }
  fieldset {
    border: 0;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  legend {
    font-family: var(--font-display);
    font-style: italic;
    font-size: var(--text-lg);
    margin-bottom: 4px;
    padding: 0;
  }
  .help {
    margin: 0 0 4px;
    font-size: var(--text-xs);
    color: var(--muted);
  }
  .option {
    display: grid;
    grid-template-columns: 18px minmax(0, 1fr);
    gap: var(--space-2);
    padding: 8px;
    border-radius: 10px;
    cursor: pointer;
  }
  .option:hover {
    background: var(--raised);
  }
  .option:has(input:checked) {
    background: var(--raised);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--gold) 45%, transparent);
  }
  input[type='radio'],
  input[type='checkbox'] {
    accent-color: var(--gold);
    margin: 3px 0 0;
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .name {
    font-weight: 600;
  }
  .swatch {
    height: 6px;
    border-radius: var(--radius-pill);
  }
  .desc {
    font-size: var(--text-xs);
    color: var(--muted);
  }
  .switch,
  .volume {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: 6px 8px;
  }
  .volume span {
    width: 64px;
    color: var(--muted);
    font-size: var(--text-sm);
  }
  .volume input {
    flex: 1;
  }
</style>
