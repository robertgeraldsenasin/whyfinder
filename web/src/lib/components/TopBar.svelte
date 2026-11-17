<script lang="ts">
  import { repo } from '../format';
  import { settings } from '../settings.svelte';
  import * as sfx from '../sfx';
  import { app, type View } from '../state.svelte';
  import SettingsPanel from './SettingsPanel.svelte';
  import Wordmark from './Wordmark.svelte';

  const tabs: [View, string][] = [
    ['discover', 'Discover'],
    ['hood', 'Under the hood'],
    ['architecture', 'Architecture'],
  ];
  let open = $state(false);

  function go(view: View, event: MouseEvent): void {
    event.preventDefault();
    const doc = document as Document & { startViewTransition?: (cb: () => void) => unknown };
    if (doc.startViewTransition && !app.reducedMotion) doc.startViewTransition(() => app.go(view));
    else app.go(view);
  }

  function toggleSound(): void {
    settings.sound = !settings.sound;
    settings.save();
    sfx.unlock();
    if (settings.sound) sfx.twinkle();
  }
</script>

<header class="bar">
  <a class="brand" href="#/" onclick={(e) => go('discover', e)} aria-label="Whyfinder home">
    <svg viewBox="0 0 64 64" width="30" height="30" aria-hidden="true">
      <g stroke="var(--violet-text)" stroke-width="2.2" stroke-linecap="round" fill="none" opacity="0.9">
        <path d="M14 16 L31 30" /><path d="M50 12 L31 30" /><path d="M31 30 L32 47" />
      </g>
      <g fill="var(--starlight)"><circle cx="14" cy="16" r="3.6" /><circle cx="50" cy="12" r="3.6" /><circle cx="31" cy="30" r="3.2" /></g>
      <path fill="var(--gold)" d="M32 38 L34.4 45.6 L42 48 L34.4 50.4 L32 58 L29.6 50.4 L22 48 L29.6 45.6 Z" />
    </svg>
    {#if !(app.view === 'discover' && app.history.length === 0)}<Wordmark size={21} />{/if}
  </a>
  <nav aria-label="Views">
    {#each tabs as [view, label] (view)}
      <a href={view === 'discover' ? '#/' : `#/${view}`} aria-current={app.view === view ? 'page' : undefined} onclick={(e) => go(view, e)}
        >{label}</a
      >
    {/each}
  </nav>
  <div class="tools">
    <button class="icon" onclick={toggleSound} aria-pressed={settings.sound} aria-label="Sound effects">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path class="speaker" d="M4 9.5 H7.5 L12 5.5 V18.5 L7.5 14.5 H4 Z" />
        {#if settings.sound}
          <path class="wave" d="M15.5 9 Q17.5 12 15.5 15" /><path class="wave" d="M18 6.5 Q21.5 12 18 17.5" />
        {:else}
          <path class="wave" d="M16 9.5 L21 14.5 M21 9.5 L16 14.5" />
        {/if}
      </svg>
    </button>
    <div class="settings">
      <button class="icon" onclick={() => (open = !open)} aria-expanded={open} aria-controls="settings-panel" aria-label="Settings">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="3.2" />
          <path
            d="M12 2.8 L13.4 5.2 L16.1 4.4 L16.6 7.2 L19.4 7.8 L18.6 10.5 L21 12 L18.6 13.5 L19.4 16.2 L16.6 16.8 L16.1 19.6 L13.4 18.8 L12 21.2 L10.6 18.8 L7.9 19.6 L7.4 16.8 L4.6 16.2 L5.4 13.5 L3 12 L5.4 10.5 L4.6 7.8 L7.4 7.2 L7.9 4.4 L10.6 5.2 Z"
          />
        </svg>
      </button>
      {#if open}
        <SettingsPanel onclose={() => (open = false)} />
      {/if}
    </div>
    <a class="gh" href={repo} target="_blank" rel="noreferrer">Source on GitHub</a>
  </div>
</header>

<style>
  .bar {
    position: relative;
    z-index: 10;
    display: flex;
    align-items: center;
    gap: var(--space-5);
    height: 72px;
    padding: 0 var(--space-5);
    background: linear-gradient(var(--bg), color-mix(in srgb, var(--bg) 0%, transparent));
  }
  .brand {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: var(--text);
    text-decoration: none;
  }
  nav {
    display: flex;
    gap: var(--space-2);
    margin-left: auto;
  }
  nav a {
    position: relative;
    color: var(--muted);
    text-decoration: none;
    padding: 10px 14px 8px;
    font-size: var(--text-sm);
    font-weight: 600;
    transition: color var(--dur-fast);
  }
  nav a:hover {
    color: var(--text);
  }
  nav a[aria-current='page'] {
    color: var(--gold-bright);
  }
  nav a[aria-current='page']::after {
    content: '';
    position: absolute;
    left: 14px;
    right: 14px;
    bottom: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--gold), transparent);
  }
  nav a[aria-current='page']::before {
    content: '';
    position: absolute;
    left: 50%;
    bottom: -3px;
    width: 6px;
    height: 6px;
    background: var(--gold);
    transform: translateX(-50%) rotate(45deg);
  }
  .tools {
    display: flex;
    gap: var(--space-2);
    align-items: center;
  }
  .settings {
    position: relative;
  }
  .icon {
    width: 38px;
    height: 38px;
    display: grid;
    place-items: center;
    border: var(--border);
    background: color-mix(in srgb, var(--deep) 80%, transparent);
    color: var(--text);
    cursor: pointer;
  }
  .icon:hover,
  .icon[aria-expanded='true'] {
    border-color: var(--gold);
  }
  .icon svg {
    width: 19px;
    height: 19px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.6;
    stroke-linejoin: round;
    stroke-linecap: round;
  }
  .icon .speaker {
    fill: currentColor;
  }
  .gh {
    margin-left: var(--space-2);
    color: var(--muted);
    font-size: var(--text-sm);
    text-decoration: none;
  }
  .gh:hover {
    color: var(--text);
  }
  @media (max-width: 900px) {
    .bar {
      flex-wrap: wrap;
      height: auto;
      gap: var(--space-3);
      padding: var(--space-3);
    }
    nav {
      order: 3;
      width: 100%;
      margin: 0;
      justify-content: space-between;
    }
    nav a {
      padding: 6px 10px;
    }
    .tools {
      margin-left: auto;
    }
    .gh {
      display: none;
    }
  }
</style>
