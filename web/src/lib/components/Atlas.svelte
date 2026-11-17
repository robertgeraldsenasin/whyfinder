<script lang="ts">
  /**
   * The atlas: a full-bleed canvas behind every view (ADR-0016). Stars are games at their layout
   * positions; lines exist only where the engine computed a reason. The loop sleeps when nothing
   * moves; with reduced motion the camera jumps and nothing flows.
   */
  import { onMount } from 'svelte';
  import { app, type Scene } from '../state.svelte';

  let canvas: HTMLCanvasElement;
  let markers: HTMLDivElement;
  let hovered = $state<number | null>(null);
  let tooltip = $state<{ x: number; y: number } | null>(null);

  // Camera in map units; the spring chases the target.
  const cam = { x: 0.5, y: 0.5, zoom: 1, vx: 0, vy: 0, vz: 0 };
  const target = { x: 0.5, y: 0.5, zoom: 1 };
  let userMoved = false;
  let stage = { x: 0, y: 0, w: 1, h: 1 };
  let width = 1;
  let height = 1;
  let dpr = 1;
  let pointer = { x: 0, y: 0 };
  let colors: Record<string, string> = {};
  let drawStart = 0;
  let sceneKey = '';
  let raf = 0;
  let last = 0;
  let maxPlays = 1;

  const layers = Array.from({ length: 3 }, (_, layer) => {
    let seed = 1234 + layer * 977;
    const rand = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
    return Array.from({ length: [260, 160, 70][layer] }, () => ({
      x: rand() * 2048,
      y: rand() * 2048,
      r: [0.5, 0.8, 1.2][layer] * (0.6 + rand() * 0.8),
      a: 0.25 + rand() * 0.45,
    }));
  });

  function readColors(): void {
    const css = getComputedStyle(document.documentElement);
    for (const k of ['bg', 'surface', 'line', 'text', 'muted', 'pick', 'link', 'nebula', 'good', 'bad', 'star']) {
      colors[k] = css.getPropertyValue(`--${k}`).trim() || '#fff';
    }
  }

  function measureStage(): void {
    const el = document.querySelector<HTMLElement>('[data-stage]');
    const r = el?.getBoundingClientRect();
    stage = r && r.width > 40 && r.height > 40 ? { x: r.left, y: r.top, w: r.width, h: r.height } : { x: 0, y: 0, w: width, h: height };
  }

  const scale = () => cam.zoom * Math.min(stage.w, stage.h) * 0.94;
  const toScreen = (x: number, y: number): [number, number] => [
    stage.x + stage.w / 2 + (x - cam.x) * scale(),
    stage.y + stage.h / 2 + (y - cam.y) * scale(),
  ];
  const toMap = (sx: number, sy: number): [number, number] => [
    cam.x + (sx - stage.x - stage.w / 2) / scale(),
    cam.y + (sy - stage.y - stage.h / 2) / scale(),
  ];

  function frame(scene: Scene): void {
    const games = app.slice?.games;
    if (!games || scene.focus.length === 0) {
      Object.assign(target, { x: 0.5, y: 0.5, zoom: 1 });
      return;
    }
    let x0 = 1, y0 = 1, x1 = 0, y1 = 0;
    for (const i of scene.focus) {
      x0 = Math.min(x0, games[i].x);
      y0 = Math.min(y0, games[i].y);
      x1 = Math.max(x1, games[i].x);
      y1 = Math.max(y1, games[i].y);
    }
    const span = Math.max(x1 - x0, y1 - y0, 0.12) + 0.1;
    Object.assign(target, { x: (x0 + x1) / 2, y: (y0 + y1) / 2, zoom: Math.min(5, Math.max(1, 1 / span)) });
  }

  function step(dt: number): boolean {
    if (app.reducedMotion) {
      Object.assign(cam, target, { vx: 0, vy: 0, vz: 0 });
      return false;
    }
    const k = 70;
    const d = 2 * Math.sqrt(k);
    let moving = false;
    for (const [p, v] of [['x', 'vx'], ['y', 'vy'], ['zoom', 'vz']] as const) {
      const a = k * (target[p] - cam[p]) - d * cam[v];
      cam[v] += a * dt;
      cam[p] += cam[v] * dt;
      if (Math.abs(target[p] - cam[p]) > 1e-4 || Math.abs(cam[v]) > 1e-4) moving = true;
    }
    return moving;
  }

  function sparkle(ctx: CanvasRenderingContext2D, x: number, y: number, r: number): void {
    ctx.beginPath();
    ctx.moveTo(x, y - r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.quadraticCurveTo(x, y, x, y + r);
    ctx.quadraticCurveTo(x, y, x - r, y);
    ctx.quadraticCurveTo(x, y, x, y - r);
    ctx.fill();
  }

  type Box = [number, number, number, number];
  let placed: Box[] = [];
  let monoFont = '';

  /** Draw a mono label unless it would overlap one already placed (higher priority first). */
  function label(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, color: string, weight = 500, force = false): void {
    ctx.font = `${weight} 11px ${monoFont}`;
    if ('letterSpacing' in ctx) (ctx as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing = '0.8px';
    const t = (text.length > 34 ? `${text.slice(0, 32)}…` : text).toUpperCase();
    const w = ctx.measureText(t).width;
    const box: Box = [x - w / 2 - 3, y - 10, x + w / 2 + 3, y + 4];
    if (!force && placed.some((b) => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1])) return;
    placed.push(box);
    ctx.fillStyle = colors.bg;
    ctx.globalAlpha = 0.75;
    ctx.fillRect(box[0], y - 9, w + 6, 13);
    ctx.globalAlpha = 1;
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.fillText(t, x, y);
  }

  function draw(time: number): void {
    const ctx = canvas.getContext('2d');
    const games = app.slice?.games;
    if (!ctx) return;
    const scene = app.scene;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = colors.bg;
    ctx.fillRect(0, 0, width, height);
    const still = app.reducedMotion;

    // Nebula wash (≤ 12% opacity), parallax 0.3.
    for (const [nx, ny, nr, a] of [[0.22, 0.3, 0.55, 0.12], [0.8, 0.7, 0.5, 0.09], [0.6, 0.12, 0.35, 0.06]]) {
      const [sx, sy] = [width * nx - (cam.x - 0.5) * 120, height * ny - (cam.y - 0.5) * 120];
      const g = ctx.createRadialGradient(sx, sy, 0, sx, sy, Math.max(width, height) * nr);
      g.addColorStop(0, colors.nebula);
      g.addColorStop(1, 'transparent');
      ctx.globalAlpha = a;
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, width, height);
    }

    // Starfield: three depths drifting with the camera and, gently, the pointer.
    const drift = still ? 0 : time / 4000;
    ctx.fillStyle = colors.star;
    layers.forEach((layer, depth) => {
      const f = [0.04, 0.09, 0.16][depth];
      const ox = -(cam.x * 900 + (still ? 0 : (pointer.x - width / 2) * 0.02)) * f + drift * (depth + 1);
      const oy = -(cam.y * 900 + (still ? 0 : (pointer.y - height / 2) * 0.02)) * f;
      for (const s of layer) {
        const x = (((s.x + ox) % 2048) + 2048) % 2048;
        const y = (((s.y + oy) % 2048) + 2048) % 2048;
        for (let tx = x; tx < width; tx += 2048) {
          for (let ty = y; ty < height; ty += 2048) {
            ctx.globalAlpha = s.a * 0.55;
            ctx.beginPath();
            ctx.arc(tx, ty, s.r, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }
    });
    ctx.globalAlpha = 1;
    if (!games) return;

    const zoomR = Math.min(1.8, 0.85 + cam.zoom * 0.25);
    const special = new Set([...scene.history, ...scene.picks]);

    // Game stars.
    games.forEach((g, i) => {
      if (special.has(i)) return;
      const [x, y] = toScreen(g.x, g.y);
      if (x < -20 || y < -20 || x > width + 20 || y > height + 20) return;
      const glow = scene.glow?.[i] ?? 0;
      const r = (0.7 + 1.9 * Math.sqrt(g.plays / maxPlays)) * zoomR;
      if (glow > 0.01) {
        ctx.globalAlpha = Math.min(0.4, glow * 0.4);
        ctx.fillStyle = colors.link;
        ctx.beginPath();
        ctx.arc(x, y, r + 1.5 + glow * 4, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = (0.35 + 0.45 * Math.sqrt(g.plays / maxPlays)) * (1 - scene.dim * 0.6) + glow * 0.4;
      ctx.fillStyle = glow > 0.01 ? colors.link : colors.star;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;

    // Hubs (tags, developers, publishers) when a view asks for them.
    const hubs = app.ready?.hubs ?? [];
    const hubAt = (node: number) => hubs[node - (app.slice?.games.length ?? 0)];
    for (const node of scene.hubs) {
      const h = hubAt(node);
      if (!h) continue;
      const [x, y] = toScreen(h.x, h.y);
      const glow = scene.hubGlow?.get(node) ?? 0;
      ctx.strokeStyle = colors.link;
      ctx.globalAlpha = 0.45 + glow * 0.55;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, y - 5);
      ctx.lineTo(x + 5, y);
      ctx.lineTo(x, y + 5);
      ctx.lineTo(x - 5, y);
      ctx.closePath();
      ctx.stroke();
      if (glow > 0.02) {
        ctx.globalAlpha = glow * 0.35;
        ctx.fillStyle = colors.link;
        ctx.fill();
      }
      ctx.globalAlpha = 1;
    }

    // Lines: draw in, then light flows from your game to the pick.
    const progress = still ? 1 : Math.min(1, (time - drawStart) / 600);
    const ease = 1 - (1 - progress) ** 3;
    for (const line of scene.lines) {
      const a = games[line.from];
      const b = games[line.to];
      let [x0, y0] = toScreen(a.x, a.y);
      let [x1, y1] = toScreen(b.x, b.y);
      if (line.kind === 'related' && line.hub !== undefined && hubAt(line.hub)) {
        const h = hubAt(line.hub);
        const [hx, hy] = toScreen(h.x, h.y);
        ctx.setLineDash([3, 4]);
        ctx.strokeStyle = colors.link;
        ctx.globalAlpha = 0.7;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x0 + (hx - x0) * ease, y0 + (hy - y0) * ease);
        ctx.moveTo(x1, y1);
        ctx.lineTo(x1 + (hx - x1) * ease, y1 + (hy - y1) * ease);
        ctx.stroke();
        ctx.setLineDash([]);
        continue;
      }
      if (line.kind === 'negative') ctx.setLineDash([2, 5]);
      ctx.strokeStyle = line.kind === 'negative' ? colors.bad : colors.link;
      ctx.globalAlpha = line.kind === 'neighbor' ? 0.55 : 0.85;
      ctx.lineWidth = line.kind === 'neighbor' ? 1 : 1 + 3 * line.share;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(x0, y0);
      [x1, y1] = [x0 + (x1 - x0) * ease, y0 + (y1 - y0) * ease];
      ctx.lineTo(x1, y1);
      ctx.stroke();
      ctx.setLineDash([]);
      if (!still && progress >= 1 && line.kind === 'reason') {
        const count = Math.ceil(2 + 10 * line.share);
        const len = Math.hypot(x1 - x0, y1 - y0);
        for (let p = 0; p < count; p++) {
          const t = ((time / (900 + len * 4)) + p / count) % 1;
          ctx.globalAlpha = Math.sin(Math.PI * t) * 0.95;
          ctx.fillStyle = colors.link;
          ctx.beginPath();
          ctx.arc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, 1.2 + line.share * 1.6, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }
    ctx.globalAlpha = 1;

    // History stars (white) and picks (amber sparkles).
    for (const i of scene.history) {
      const [x, y] = toScreen(games[i].x, games[i].y);
      ctx.fillStyle = colors.star;
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = colors.star;
      ctx.globalAlpha = 0.35;
      ctx.beginPath();
      ctx.arc(x, y, 8, 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
    scene.picks.forEach((i) => {
      const [x, y] = toScreen(games[i].x, games[i].y);
      const selected = scene.selected === i;
      if (selected && !still) {
        const pulse = (Math.sin(time / 380) + 1) / 2;
        const g = ctx.createRadialGradient(x, y, 0, x, y, 22);
        g.addColorStop(0, colors.pick);
        g.addColorStop(1, 'transparent');
        ctx.globalAlpha = 0.25 + pulse * 0.2;
        ctx.fillStyle = g;
        ctx.fillRect(x - 24, y - 24, 48, 48);
        ctx.globalAlpha = 1;
      }
      ctx.fillStyle = colors.pick;
      ctx.globalAlpha = selected || scene.selected === null ? 1 : 0.7;
      sparkle(ctx, x, y, selected ? 10 : 7);
      ctx.globalAlpha = 1;
    });

    // Labels by priority: the selected pick, your games, hubs, then pick ranks; no overlaps.
    placed = [];
    monoFont = getComputedStyle(document.documentElement).getPropertyValue('--font-mono');
    if (scene.selected !== null) {
      const [x, y] = toScreen(games[scene.selected].x, games[scene.selected].y);
      label(ctx, games[scene.selected].title, x, y - 16, colors.pick, 600, true);
    }
    for (const i of scene.history) {
      const [x, y] = toScreen(games[i].x, games[i].y);
      label(ctx, games[i].title, x, y + 20, colors.text, 500, true);
    }
    for (const node of scene.hubs.slice(0, 8)) {
      const h = hubAt(node);
      if (!h) continue;
      const [x, y] = toScreen(h.x, h.y);
      label(ctx, h.name, x, y - 9, colors.muted);
    }
    scene.picks.forEach((i, rank) => {
      if (scene.selected === i) return;
      const [x, y] = toScreen(games[i].x, games[i].y);
      label(ctx, String(rank + 1).padStart(2, '0'), x + 14, y - 6, colors.pick);
    });
    if (hovered !== null && !special.has(hovered)) {
      const [x, y] = toScreen(games[hovered].x, games[hovered].y);
      ctx.strokeStyle = colors.pick;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(x, y, 7, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Keep keyboard markers on top of their stars.
    for (const el of markers.querySelectorAll<HTMLElement>('[data-game]')) {
      const g = games[Number(el.dataset.game)];
      const [x, y] = toScreen(g.x, g.y);
      el.style.transform = `translate(${x - 11}px, ${y - 11}px)`;
    }
    const anchor = document.querySelector<HTMLElement>('[data-anchor-game]');
    if (anchor) {
      const g = games[Number(anchor.dataset.anchorGame)];
      const [x, y] = toScreen(g.x, g.y);
      anchor.style.transform = `translate(${Math.round(x + 14)}px, ${Math.round(y - 14)}px)`;
    }
  }

  function loop(time: number): void {
    const dt = Math.min(0.05, last ? (time - last) / 1000 : 0.016);
    last = time;
    const moving = step(dt);
    draw(time);
    const flowing = !app.reducedMotion && (app.scene.lines.length > 0 || app.scene.selected !== null);
    const drawing = time - drawStart < 650;
    raf = 0;
    if (document.hidden) return;
    if (moving || flowing || drawing) raf = requestAnimationFrame(loop);
    else if (!app.reducedMotion) idle = setTimeout(() => ((idle = 0), (raf = requestAnimationFrame(loop))), 120); // slow drift ~8 fps
  }

  let idle: ReturnType<typeof setTimeout> | 0 = 0;
  function wake(): void {
    if (idle) {
      clearTimeout(idle);
      idle = 0;
    }
    if (!raf && !document.hidden) {
      last = 0;
      raf = requestAnimationFrame(loop);
    }
  }

  function resize(): void {
    dpr = Math.min(2, window.devicePixelRatio || 1);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    measureStage();
    wake();
  }

  function nearest(sx: number, sy: number): number | null {
    const games = app.slice?.games;
    if (!games) return null;
    let best: number | null = null;
    let bestD = 14 * 14;
    games.forEach((g, i) => {
      const [x, y] = toScreen(g.x, g.y);
      const d = (x - sx) ** 2 + (y - sy) ** 2;
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    });
    return best;
  }

  let drag: { x: number; y: number; cx: number; cy: number; moved: boolean } | null = null;

  function onPointerDown(e: PointerEvent): void {
    drag = { x: e.clientX, y: e.clientY, cx: target.x, cy: target.y, moved: false };
  }
  function onPointerMove(e: PointerEvent): void {
    pointer = { x: e.clientX, y: e.clientY };
    if (drag && e.buttons) {
      const dx = (e.clientX - drag.x) / scale();
      const dy = (e.clientY - drag.y) / scale();
      if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) > 4) drag.moved = true;
      target.x = drag.cx - dx;
      target.y = drag.cy - dy;
      if (app.reducedMotion) Object.assign(cam, target);
      userMoved = true;
    }
    hovered = nearest(e.clientX, e.clientY);
    tooltip = hovered !== null ? { x: e.clientX, y: e.clientY } : null;
    wake();
  }
  function onPointerUp(e: PointerEvent): void {
    if (drag && !drag.moved) {
      const hit = nearest(e.clientX, e.clientY);
      app.inspect = hit;
    }
    drag = null;
  }
  function onWheel(e: WheelEvent): void {
    e.preventDefault();
    const [mx, my] = toMap(e.clientX, e.clientY);
    const factor = Math.exp(-e.deltaY * 0.0015);
    const zoom = Math.min(8, Math.max(0.7, target.zoom * factor));
    target.x = mx - (mx - target.x) * (target.zoom / zoom);
    target.y = my - (my - target.y) * (target.zoom / zoom);
    target.zoom = zoom;
    if (app.reducedMotion) Object.assign(cam, target);
    userMoved = true;
    wake();
  }

  export function recenter(): void {
    userMoved = false;
    frame(app.scene);
    wake();
  }

  $effect(() => {
    const scene = app.scene;
    if (scene.key !== sceneKey) {
      sceneKey = scene.key;
      drawStart = performance.now();
      measureStage();
      if (!userMoved || scene.focus.length) {
        userMoved = false;
        frame(scene);
      }
    }
    wake();
  });

  $effect(() => {
    void app.theme;
    requestAnimationFrame(() => {
      readColors();
      wake();
    });
  });

  $effect(() => {
    void app.view;
    void app.history.length;
    void app.result;
    requestAnimationFrame(() => {
      measureStage();
      wake();
    });
  });

  $effect(() => {
    const games = app.slice?.games;
    if (games) maxPlays = Math.max(...games.map((g) => g.plays));
    wake();
  });

  onMount(() => {
    readColors();
    resize();
    const ro = new ResizeObserver(() => {
      measureStage();
      wake();
    });
    ro.observe(document.body);
    const onVisible = () => wake();
    window.addEventListener('resize', resize);
    document.addEventListener('visibilitychange', onVisible);
    canvas.addEventListener('wheel', onWheel, { passive: false });
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', resize);
      document.removeEventListener('visibilitychange', onVisible);
      cancelAnimationFrame(raf);
      if (idle) clearTimeout(idle);
    };
  });
</script>

<canvas
  bind:this={canvas}
  class="atlas"
  aria-hidden="true"
  onpointerdown={onPointerDown}
  onpointermove={onPointerMove}
  onpointerup={onPointerUp}
  onpointerleave={() => {
    hovered = null;
    tooltip = null;
  }}
></canvas>

<div class="markers" bind:this={markers}>
  {#if app.slice}
    {#each app.scene.picks as i, rank (i)}
      <button
        class="marker"
        data-game={i}
        aria-label={`Pick ${rank + 1}: ${app.slice.games[i].title}`}
        aria-pressed={app.scene.selected === i}
        onclick={() => (app.selected = rank)}
      ></button>
    {/each}
  {/if}
</div>

{#if tooltip && hovered !== null && app.slice}
  <div class="tooltip mono" style:left={`${tooltip.x + 14}px`} style:top={`${tooltip.y + 14}px`} aria-hidden="true">
    {app.slice.games[hovered].title}
  </div>
{/if}

<style>
  .atlas {
    position: fixed;
    inset: 0;
    z-index: 0;
    cursor: grab;
    touch-action: none;
  }
  .atlas:active {
    cursor: grabbing;
  }
  .markers {
    position: fixed;
    inset: 0;
    z-index: 1;
    pointer-events: none;
  }
  .marker {
    position: absolute;
    left: 0;
    top: 0;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    border: 0;
    background: transparent;
    pointer-events: auto;
    cursor: pointer;
  }
  .tooltip {
    position: fixed;
    z-index: 30;
    pointer-events: none;
    background: var(--surface);
    color: var(--text);
    border: var(--border);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
</style>
