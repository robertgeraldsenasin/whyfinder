<script lang="ts">
  import { onMount } from 'svelte';
  import { type Flashes, settings } from '../settings.svelte';
  import * as sfx from '../sfx';
  import { gradient, PALETTES } from '../sky';

  let { onclose }: { onclose: () => void } = $props();
  let panel: HTMLDivElement;

  const EFFECTS: { id: Flashes; name: string; description: string }[] = [
    { id: 'full', name: 'Full', description: 'Brief full-screen impact frames, shake and confetti, never more than three flashes a second.' },
    { id: 'reduced', name: 'Reduced flashing', description: 'Bursts stay around the card; gentler shake.' },
    { id: 'off', name: 'Off', description: 'No flashes, no shake and no confetti.' },
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

<div class="panel hud pop" id="settings-panel" role="dialog" aria-label="Settings" bind:this={panel}>
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
    <p class="help">If your device asks for reduced motion, the cards appear in place with no effects at all.</p>
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
    box-shadow:
      6px 6px 0 var(--crimson),
      0 24px 60px -20px rgb(0 0 0 / 0.9);
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
    font-family: var(--font-poster);
    font-size: 17px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
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
    border-radius: 0;
    cursor: pointer;
  }
  .option:hover {
    background: var(--raised);
  }
  .option:has(input:checked) {
    background: var(--raised);
    box-shadow: inset 3px 0 0 var(--crimson);
  }
  input[type='radio'],
  input[type='checkbox'] {
    accent-color: var(--crimson);
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
    transform: skewX(-20deg);
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
