<script lang="ts">
  import { repo } from '../format';
  import { app, type View } from '../state.svelte';

  const tabs: [View, string][] = [
    ['discover', 'Discover'],
    ['hood', 'Under the hood'],
    ['architecture', 'Architecture'],
  ];

  function go(view: View, event: MouseEvent): void {
    event.preventDefault();
    const doc = document as Document & { startViewTransition?: (cb: () => void) => unknown };
    if (doc.startViewTransition && !app.reducedMotion) doc.startViewTransition(() => app.go(view));
    else app.go(view);
  }
</script>

<header class="bar">
  <a class="brand" href="#/" onclick={(e) => go('discover', e)} aria-label="Whyfinder home">
    <svg viewBox="0 0 64 64" width="30" height="30" aria-hidden="true">
      <g stroke="var(--link)" stroke-width="2.4" stroke-linecap="round" fill="none">
        <path d="M16 14 L32 31" /><path d="M48 14 L32 31" /><path d="M32 31 L32 50" />
      </g>
      <g fill="var(--star)"><circle cx="16" cy="14" r="4" /><circle cx="48" cy="14" r="4" /><circle cx="32" cy="31" r="3.6" /></g>
      <path fill="var(--pick)" d="M32 41.5 L34.1 47.9 L40.5 50 L34.1 52.1 L32 58.5 L29.9 52.1 L23.5 50 L29.9 47.9 Z" />
    </svg>
    <span class="word">whyfinder</span>
  </a>
  <nav aria-label="Views">
    {#each tabs as [view, label] (view)}
      <a
        href={view === 'discover' ? '#/' : `#/${view}`}
        aria-current={app.view === view ? 'page' : undefined}
        onclick={(e) => go(view, e)}>{label}</a
      >
    {/each}
  </nav>
  <div class="tools">
    <button
      class="theme micro"
      onclick={() => app.setTheme(app.theme === 'deep-field' ? 'atlas-paper' : 'deep-field')}
      aria-label={`Switch to ${app.theme === 'deep-field' ? 'Atlas Paper (light)' : 'Deep Field (dark)'} theme`}
    >
      {app.theme === 'deep-field' ? 'Atlas paper' : 'Deep field'}
    </button>
    <a class="gh" href={repo} target="_blank" rel="noreferrer">GitHub</a>
  </div>
</header>

<style>
  .bar {
    position: relative;
    z-index: 10;
    display: flex;
    align-items: center;
    gap: var(--space-5);
    padding: var(--space-3) var(--space-5);
    background: linear-gradient(var(--bg), color-mix(in srgb, var(--bg) 0%, transparent));
  }
  .brand {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: var(--text);
    text-decoration: none;
  }
  .word {
    font-family: var(--font-display);
    font-weight: 600;
    font-size: 22px;
    letter-spacing: -0.01em;
  }
  nav {
    display: flex;
    gap: 4px;
    margin-left: auto;
    background: var(--surface);
    border: var(--border);
    border-radius: 10px;
    padding: 4px;
  }
  nav a {
    color: var(--muted);
    text-decoration: none;
    padding: 6px 14px;
    border-radius: 7px;
    font-size: var(--text-sm);
    transition:
      color var(--dur-fast),
      background var(--dur-fast);
  }
  nav a:hover {
    color: var(--text);
  }
  nav a[aria-current='page'] {
    background: var(--raised);
    color: var(--text);
  }
  .tools {
    display: flex;
    gap: var(--space-3);
    align-items: center;
  }
  .theme {
    background: var(--surface);
    border: var(--border);
    border-radius: var(--radius-pill);
    padding: 6px 14px;
    color: var(--text);
    cursor: pointer;
  }
  .gh {
    color: var(--muted);
    font-size: var(--text-sm);
    text-decoration: none;
  }
  .gh:hover {
    color: var(--text);
  }
  @media (max-width: 860px) {
    .bar {
      flex-wrap: wrap;
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
      padding: 6px 8px;
    }
    .tools {
      margin-left: auto;
    }
  }
</style>
