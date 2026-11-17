<script lang="ts">
  /**
   * The sky behind every view (ADR-0016, ADR-0017). Each star is a game at its layout position.
   * When results arrive the picks fall from the sky, #10 first and #1 last: a lock-on beam, a
   * streak, an impact (with a brief impact frame for the top three), shockwaves, embers and a
   * shake. Then the whole sky recolours by closeness, rippling out from your games, and lines show
   * the exact reasons for the selected pick.
   *
   * Reduced motion: no fall, no shake, no flashes, no twinkle; everything appears in place.
   * Impact frames are capped at three per second whatever the settings.
   */
  import { onMount } from 'svelte';
  import * as sfx from '../sfx';
  import { settings } from '../settings.svelte';
  import { colorAt } from '../sky';
  import { app, type Scene } from '../state.svelte';

  let canvas: HTMLCanvasElement;
  let overlay: HTMLCanvasElement;
  let markers: HTMLDivElement;
  let hovered = $state<number | null>(null);
  let tooltip = $state<{ x: number; y: number } | null>(null);

  const C = {
    midnight: '#070b1e',
    starlight: '#f5f2ff',
    gold: '#f2c14e',
    goldBright: '#ffe39a',
    violet: '#8e6bf0',
    violetText: '#b8a4ff',
    ember: '#ff9a4d',
    bad: '#ff8f8f',
    dust: '#a9aed3',
  };

  // Camera in map units; a critically damped spring chases the target.
  const cam = { x: 0.5, y: 0.5, zoom: 1, vx: 0, vy: 0, vz: 0 };
  const target = { x: 0.5, y: 0.5, zoom: 1 };
  let userMoved = false;
  let stage = { x: 0, y: 0, w: 1, h: 1 };
  let width = 1;
  let height = 1;
  let dpr = 1;
  let pointer = { x: 0, y: 0 };
  let sceneKey = '';
  let drawStart = 0;
  let raf = 0;
  let last = 0;
  let maxPlays = 1;
  let byPlays: number[] = [];
  let shake = { x: 0, y: 0 };

  // ---------- sprites ----------
  const spriteCache = new Map<string, HTMLCanvasElement>();
  function glowSprite(color: string): HTMLCanvasElement {
    const key = `g${color}`;
    let s = spriteCache.get(key);
    if (s) return s;
    s = document.createElement('canvas');
    s.width = s.height = 64;
    const g = s.getContext('2d')!;
    const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, '#ffffff');
    grad.addColorStop(0.09, color);
    grad.addColorStop(0.22, `${color}88`);
    grad.addColorStop(0.5, `${color}1c`);
    grad.addColorStop(1, `${color}00`);
    g.fillStyle = grad;
    g.fillRect(0, 0, 64, 64);
    spriteCache.set(key, s);
    return s;
  }
  function spikeSprite(color: string): HTMLCanvasElement {
    const key = `s${color}`;
    let s = spriteCache.get(key);
    if (s) return s;
    s = document.createElement('canvas');
    s.width = s.height = 128;
    const g = s.getContext('2d')!;
    for (const [dx, dy] of [
      [1, 0],
      [0, 1],
    ]) {
      const grad = g.createLinearGradient(64 - 64 * dx, 64 - 64 * dy, 64 + 64 * dx, 64 + 64 * dy);
      grad.addColorStop(0, `${color}00`);
      grad.addColorStop(0.5, '#ffffff');
      grad.addColorStop(1, `${color}00`);
      g.fillStyle = grad;
      if (dx) g.fillRect(0, 63, 128, 2);
      else g.fillRect(63, 0, 2, 128);
    }
    spriteCache.set(key, s);
    return s;
  }
  function drawGlow(ctx: CanvasRenderingContext2D, color: string, x: number, y: number, r: number, alpha: number): void {
    if (alpha <= 0.003) return;
    ctx.globalAlpha = Math.min(1, alpha);
    const size = r * 8;
    ctx.drawImage(glowSprite(color), x - size / 2, y - size / 2, size, size);
  }
  function drawSpikes(ctx: CanvasRenderingContext2D, color: string, x: number, y: number, len: number, alpha: number): void {
    ctx.globalAlpha = Math.min(1, alpha);
    ctx.drawImage(spikeSprite(color), x - len, y - len, len * 2, len * 2);
  }

  // Closeness colours, quantized so each colour needs one sprite.
  const LEVELS = 32;
  let paletteColors: string[] = [];
  let paletteFor = '';
  function closenessColor(c: number): string {
    if (paletteFor !== settings.palette) {
      paletteFor = settings.palette;
      paletteColors = Array.from({ length: LEVELS + 1 }, (_, k) => colorAt(settings.palette, k / LEVELS));
    }
    return paletteColors[Math.round(Math.min(1, Math.max(0, c)) * LEVELS)];
  }
  // Star temperatures for the resting sky: blue-white, white, warm white, pale gold.
  const NEUTRAL = ['#c9d6ff', '#eeeaff', '#fff0d6', '#ffe2a3'];

  // ---------- background ----------
  let nebula: HTMLCanvasElement | null = null;
  function buildNebula(): void {
    nebula = document.createElement('canvas');
    const w = Math.ceil(width * 1.25);
    const h = Math.ceil(height * 1.25);
    nebula.width = w;
    nebula.height = h;
    const g = nebula.getContext('2d')!;
    let seed = 99;
    const rand = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
    const blob = (x: number, y: number, r: number, color: string, a: number) => {
      const grad = g.createRadialGradient(x, y, 0, x, y, r);
      grad.addColorStop(0, color);
      grad.addColorStop(1, `${color}00`);
      g.globalAlpha = a;
      g.fillStyle = grad;
      g.fillRect(x - r, y - r, r * 2, r * 2);
    };
    const d = Math.max(w, h);
    blob(w * 0.18, h * 0.22, d * 0.55, '#1b2a7a', 0.55);
    blob(w * 0.85, h * 0.8, d * 0.5, '#2a1c6e', 0.55);
    blob(w * 0.25, h * 0.35, d * 0.32, C.violet, 0.14);
    blob(w * 0.75, h * 0.62, d * 0.28, C.violet, 0.1);
    blob(w * 0.55, h * 0.48, d * 0.22, '#3d5bd9', 0.08);
    // A faint milky band across the diagonal, made of many soft puffs.
    for (let k = 0; k < 70; k++) {
      const t = rand();
      const x = w * (-0.05 + 1.1 * t);
      const y = h * (0.95 - 0.9 * t) + (rand() - 0.5) * h * 0.22;
      blob(x, y, d * (0.04 + rand() * 0.09), k % 5 === 0 ? '#ffe9b8' : '#c9c3ff', 0.035 + rand() * 0.03);
    }
    g.globalAlpha = 1;
  }

  // Three depths of background stars, each with its own twinkle.
  const layers = Array.from({ length: 3 }, (_, layer) => {
    let seed = 1234 + layer * 977;
    const rand = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
    return Array.from({ length: [340, 180, 70][layer] }, () => ({
      x: rand() * 2048,
      y: rand() * 2048,
      r: [0.45, 0.7, 1.1][layer] * (0.6 + rand() * 0.8),
      a: 0.2 + rand() * 0.5,
      p: rand() * Math.PI * 2,
      s: 0.6 + rand() * 1.8,
      warm: rand() < 0.12,
    }));
  });
  let phases: Float32Array = new Float32Array(0);

  // ---------- camera ----------
  function measureStage(): void {
    const el = document.querySelector<HTMLElement>('[data-stage]');
    const r = el?.getBoundingClientRect();
    stage = r && r.width > 40 && r.height > 40 ? { x: r.left, y: r.top, w: r.width, h: r.height } : { x: 0, y: 0, w: width, h: height };
  }
  const scale = () => cam.zoom * Math.min(stage.w, stage.h) * 0.94;
  const toScreen = (x: number, y: number): [number, number] => [
    stage.x + stage.w / 2 + (x - cam.x) * scale() + shake.x,
    stage.y + stage.h / 2 + (y - cam.y) * scale() + shake.y,
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
    let x0 = 1,
      y0 = 1,
      x1 = 0,
      y1 = 0;
    for (const i of scene.focus) {
      x0 = Math.min(x0, games[i].x);
      y0 = Math.min(y0, games[i].y);
      x1 = Math.max(x1, games[i].x);
      y1 = Math.max(y1, games[i].y);
    }
    const span = Math.max(x1 - x0, y1 - y0, 0.12) + 0.12;
    Object.assign(target, { x: (x0 + x1) / 2, y: (y0 + y1) / 2, zoom: Math.min(5, Math.max(1, 1 / span)) });
  }

  function step(dt: number): boolean {
    if (app.reducedMotion) {
      Object.assign(cam, target, { vx: 0, vy: 0, vz: 0 });
      return false;
    }
    const k = 60;
    const d = 2 * Math.sqrt(k);
    let moving = false;
    for (const [p, v] of [
      ['x', 'vx'],
      ['y', 'vy'],
      ['zoom', 'vz'],
    ] as const) {
      const a = k * (target[p] - cam[p]) - d * cam[v];
      cam[v] += a * dt;
      cam[p] += cam[v] * dt;
      if (Math.abs(target[p] - cam[p]) > 1e-4 || Math.abs(cam[v]) > 1e-4) moving = true;
    }
    return moving;
  }

  // ---------- starfall ----------
  interface Fall {
    rank: number;
    game: number;
    spawn: number;
    impact: number;
    landed: boolean;
    locked: boolean;
    strength: number;
  }
  interface Ring {
    x: number;
    y: number;
    t0: number;
    dur: number;
    r: number;
    color: string;
    w: number;
  }
  interface Ember {
    x: number;
    y: number;
    vx: number;
    vy: number;
    t0: number;
    life: number;
    size: number;
    color: string;
  }
  interface Flash {
    x: number;
    y: number;
    t0: number;
    full: boolean;
    strength: number;
    wedges: [number, number, number][];
  }

  let falls: Fall[] = [];
  let fallKey: string | null = null;
  let rings: Ring[] = [];
  let embers: Ember[] = [];
  let flashes: Flash[] = [];
  let flashTimes: number[] = [];
  const craters = new Map<number, number>();
  let shakeStart = 0;
  let shakeAmp = 0;
  let ripple: { t0: number; delay: Float32Array } | null = null;
  let prevHistory = new Set<number>();
  let fallSeed = 1;

  const FALL_MS = 560;

  function rand(): number {
    fallSeed = (fallSeed * 16807) % 2147483647;
    return (fallSeed - 1) / 2147483646;
  }

  function startFall(scene: Scene, now: number): void {
    const n = scene.picks.length;
    falls = [];
    let t = now + 420;
    // #10 lands first; the top three are spaced so impact frames stay under three a second.
    for (let rank = n - 1; rank >= 0; rank--) {
      const top = rank < 3;
      const dur = rank === 0 ? FALL_MS + 160 : top ? FALL_MS + 60 : FALL_MS;
      const hang = rank === 0 ? 420 : 0;
      falls.push({ rank, game: scene.picks[rank], spawn: t, impact: t + hang + dur, landed: false, locked: false, strength: rank === 0 ? 1 : top ? 0.68 : 0.36 });
      t += rank <= 3 ? 430 : 150;
    }
    app.landed = 0;
    app.falling = true;
    ripple = null;
  }

  function finishFall(now: number): void {
    for (const f of falls) if (!f.landed) f.landed = true;
    falls = [];
    flashes = [];
    app.landed = app.scene.picks.length;
    app.falling = false;
    drawStart = now;
    if (!ripple) startRipple(now - 5000);
  }

  function startRipple(now: number): void {
    const games = app.slice?.games;
    const scene = app.scene;
    if (!games || !scene.closeness) return;
    const delay = new Float32Array(games.length);
    const hist = scene.history.map((j) => games[j]);
    games.forEach((g, i) => {
      let d = 2;
      for (const h of hist) d = Math.min(d, Math.hypot(g.x - h.x, g.y - h.y));
      delay[i] = d * 1500;
    });
    ripple = { t0: now, delay };
  }

  function canFlash(now: number): boolean {
    flashTimes = flashTimes.filter((t) => now - t < 1000);
    return flashTimes.length < 3;
  }

  function land(f: Fall, now: number): void {
    const g = app.slice!.games[f.game];
    f.landed = true;
    craters.set(f.game, now);
    const s = f.strength;
    rings.push({ x: g.x, y: g.y, t0: now, dur: 700, r: 50 + 150 * s, color: C.goldBright, w: 1.5 + 3 * s });
    rings.push({ x: g.x, y: g.y, t0: now + 60, dur: 1150, r: 80 + 260 * s, color: C.violet, w: 1 + 2 * s });
    if (f.rank === 0) rings.push({ x: g.x, y: g.y, t0: now + 140, dur: 1600, r: 520, color: C.starlight, w: 1 });
    const [sx, sy] = toScreen(g.x, g.y);
    const count = Math.round(16 + 64 * s);
    for (let k = 0; k < count; k++) {
      const a = -Math.PI / 2 + (rand() - 0.5) * Math.PI * 1.7;
      const v = 90 + rand() * 380 * (0.6 + s);
      embers.push({ x: sx, y: sy, vx: Math.cos(a) * v, vy: Math.sin(a) * v, t0: now, life: 500 + rand() * 900 * (0.5 + s), size: 0.8 + rand() * 2.2 * (0.5 + s), color: rand() < 0.6 ? C.gold : rand() < 0.5 ? C.ember : C.starlight });
    }
    const effects = settings.flashes;
    if (f.rank < 3 && effects !== 'off' && canFlash(now)) {
      flashTimes.push(now);
      const wedges: [number, number, number][] = Array.from({ length: 72 }, (_, k) => [
        ((k + rand() * 0.9) / 72) * Math.PI * 2,
        0.003 + rand() * rand() * 0.024,
        0.04 + rand() * 0.24,
      ]);
      flashes.push({ x: sx, y: sy, t0: now, full: effects === 'full', strength: s, wedges });
    }
    if (effects !== 'off') {
      shakeStart = now;
      shakeAmp = (effects === 'full' ? 1 : 0.5) * (1.5 + 9 * s * s);
    }
    sfx.impact(f.rank, (sx / width) * 2 - 1, s);
    app.landed = Math.max(app.landed, app.scene.picks.length - f.rank);
    if (f.rank === 0) {
      app.falling = false;
      drawStart = now + 250;
      startRipple(now);
    }
  }

  function updateFalls(now: number): void {
    for (const f of falls) {
      if (!f.locked && now >= f.spawn) {
        f.locked = true;
        const g = app.slice!.games[f.game];
        const [sx] = toScreen(g.x, g.y);
        const pan = (sx / width) * 2 - 1;
        if (f.rank === 0) sfx.lock(pan);
        const hang = f.rank === 0 ? 420 : 0;
        sfx.whoosh((f.impact - f.spawn - hang) / 1000, pan, f.strength, hang / 1000);
      }
      if (!f.landed && now >= f.impact) land(f, now);
    }
    if (falls.length && falls.every((f) => f.landed)) falls = [];
  }

  // ---------- drawing ----------
  type Box = [number, number, number, number];
  let placed: Box[] = [];
  let bodyFont = 'sans-serif';
  let displayFont = 'serif';

  function label(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, color: string, opts: { force?: boolean; display?: boolean; size?: number; alpha?: number } = {}): void {
    const size = opts.size ?? 12.5;
    ctx.font = opts.display ? `italic 600 ${size}px ${displayFont}` : `500 ${size}px ${bodyFont}`;
    const t = text.length > 38 ? `${text.slice(0, 36)}…` : text;
    const w = ctx.measureText(t).width;
    const box: Box = [x - w / 2 - 4, y - size, x + w / 2 + 4, y + 4];
    if (!opts.force && placed.some((b) => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1])) return;
    placed.push(box);
    ctx.globalAlpha = opts.alpha ?? 1;
    ctx.textAlign = 'center';
    ctx.lineJoin = 'round';
    ctx.lineWidth = 4;
    ctx.strokeStyle = 'rgba(7, 11, 30, 0.85)';
    ctx.strokeText(t, x, y);
    ctx.fillStyle = color;
    ctx.fillText(t, x, y);
    ctx.globalAlpha = 1;
  }

  function drawBackground(ctx: CanvasRenderingContext2D, time: number, still: boolean): void {
    ctx.fillStyle = C.midnight;
    ctx.fillRect(0, 0, width, height);
    if (nebula) {
      ctx.globalAlpha = 1;
      const ox = -(cam.x - 0.5) * 90 - width * 0.125 + (still ? 0 : (pointer.x - width / 2) * -0.006);
      const oy = -(cam.y - 0.5) * 90 - height * 0.125 + (still ? 0 : (pointer.y - height / 2) * -0.006);
      ctx.drawImage(nebula, ox + shake.x * 0.3, oy + shake.y * 0.3);
    }
    const drift = still ? 0 : time / 5000;
    layers.forEach((layer, depth) => {
      const f = [0.035, 0.08, 0.15][depth];
      const ox = -(cam.x * 900 + (still ? 0 : (pointer.x - width / 2) * 0.02)) * f + drift * (depth + 1) + shake.x * f * 2;
      const oy = -(cam.y * 900 + (still ? 0 : (pointer.y - height / 2) * 0.02)) * f + shake.y * f * 2;
      for (const s of layer) {
        const x = (((s.x + ox) % 2048) + 2048) % 2048;
        const y = (((s.y + oy) % 2048) + 2048) % 2048;
        const tw = still ? 1 : 0.65 + 0.35 * Math.sin(time * 0.001 * s.s + s.p);
        for (let tx = x; tx < width; tx += 2048) {
          for (let ty = y; ty < height; ty += 2048) {
            ctx.globalAlpha = s.a * tw * 0.8;
            ctx.fillStyle = s.warm ? '#ffe9b8' : '#dcdcff';
            ctx.beginPath();
            ctx.arc(tx, ty, s.r, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }
    });
    ctx.globalAlpha = 1;
  }

  function draw(time: number): void {
    const ctx = canvas.getContext('2d');
    const games = app.slice?.games;
    if (!ctx) return;
    const scene = app.scene;
    const still = app.reducedMotion;

    // Shake: a decaying wobble after each impact.
    const sAge = (time - shakeStart) / 1000;
    if (!still && shakeAmp > 0 && sAge < 0.6) {
      const a = shakeAmp * Math.exp(-sAge * 7);
      shake = { x: a * Math.sin(sAge * 90), y: a * Math.cos(sAge * 71) * 0.8 };
    } else shake = { x: 0, y: 0 };

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.globalCompositeOperation = 'source-over';
    drawBackground(ctx, time, still);
    if (!games) return;

    const zoomR = Math.min(1.9, 0.8 + cam.zoom * 0.28);
    const owned = new Set(scene.history);
    const pickSet = new Set(scene.picks);
    const hidden = new Set(falls.filter((f) => !f.landed).map((f) => f.game));
    const close = scene.closeness ?? null;
    const dim = scene.dim;

    // Game stars.
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < games.length; i++) {
      if (owned.has(i) || pickSet.has(i)) continue;
      const g = games[i];
      const [x, y] = toScreen(g.x, g.y);
      if (x < -30 || y < -30 || x > width + 30 || y > height + 30) continue;
      const pop = Math.sqrt(g.plays / maxPlays);
      const tw = still ? 1 : 0.8 + 0.2 * Math.sin(time * 0.0016 + phases[i]);
      const neutral = NEUTRAL[(i * 7 + (g.id % 13)) % 4];
      let r = (0.75 + 3.6 * pop) * zoomR;
      let alpha = (0.26 + 0.74 * pop) * (1 - dim * 0.55) * tw;
      const glow = scene.glow?.[i] ?? 0;
      if (close) {
        const c = close[i];
        const p = ripple ? Math.min(1, Math.max(0, (time - ripple.t0 - ripple.delay[i]) / 650)) : 0;
        const rc = (0.6 + 2.4 * pop) * zoomR * (0.55 + 1.25 * c * c);
        const ac = (0.16 + 0.95 * c ** 1.6) * tw;
        if (p < 1) drawGlow(ctx, neutral, x, y, r, alpha * (1 - p));
        if (p > 0) {
          drawGlow(ctx, closenessColor(c), x, y, rc * (p < 1 ? 1 + 0.8 * Math.sin(Math.PI * p) : 1), ac * p);
          if (c > 0.6 && p >= 1) drawSpikes(ctx, closenessColor(c), x, y, rc * 4 * tw, (c - 0.6) * 1.6);
        }
        continue;
      }
      if (glow > 0.01) {
        drawGlow(ctx, C.violet, x, y, r * (1.6 + glow * 2.4), Math.min(0.9, glow));
        r *= 1 + glow * 0.6;
        alpha = Math.max(alpha, 0.5 + glow * 0.5);
      }
      drawGlow(ctx, glow > 0.01 ? C.violetText : neutral, x, y, r, alpha);
      if (pop > 0.5 && dim < 0.5) drawSpikes(ctx, neutral, x, y, r * 4.5 * tw, 0.35 * tw);
    }

    // Hubs (tags, developers, publishers) when a view asks for them.
    ctx.globalCompositeOperation = 'source-over';
    const hubs = app.ready?.hubs ?? [];
    const hubAt = (node: number) => hubs[node - games.length];
    for (const node of falls.length ? [] : scene.hubs) {
      const h = hubAt(node);
      if (!h) continue;
      const [x, y] = toScreen(h.x, h.y);
      const glow = scene.hubGlow?.get(node) ?? 0;
      ctx.strokeStyle = C.violetText;
      ctx.globalAlpha = 0.5 + glow * 0.5;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(x, y - 6);
      ctx.lineTo(x + 6, y);
      ctx.lineTo(x, y + 6);
      ctx.lineTo(x - 6, y);
      ctx.closePath();
      ctx.stroke();
      if (glow > 0.02) {
        ctx.globalAlpha = glow * 0.4;
        ctx.fillStyle = C.violet;
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;

    // Your constellation: each of your games joined to the nearest one added before it.
    if (scene.history.length > 1) {
      ctx.strokeStyle = C.starlight;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.22;
      ctx.beginPath();
      scene.history.forEach((j, k) => {
        if (k === 0) return;
        let best = scene.history[0];
        let bd = Infinity;
        for (const m of scene.history.slice(0, k)) {
          const d = Math.hypot(games[m].x - games[j].x, games[m].y - games[j].y);
          if (d < bd) {
            bd = d;
            best = m;
          }
        }
        const [ax, ay] = toScreen(games[j].x, games[j].y);
        const [bx, by] = toScreen(games[best].x, games[best].y);
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
      });
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // Reasons: lines drawn in once the picks have landed, then light flows to the pick.
    const linesReady = falls.length === 0;
    const progress = still ? 1 : Math.min(1, Math.max(0, (time - drawStart) / 700));
    const ease = 1 - (1 - progress) ** 3;
    if (linesReady) {
      for (const line of scene.lines) {
        const a = games[line.from];
        const b = games[line.to];
        const [x0, y0] = toScreen(a.x, a.y);
        let [x1, y1] = toScreen(b.x, b.y);
        if (line.kind === 'related' && line.hub !== undefined && hubAt(line.hub)) {
          const h = hubAt(line.hub);
          const [hx, hy] = toScreen(h.x, h.y);
          ctx.setLineDash([3, 5]);
          ctx.strokeStyle = C.violetText;
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
        [x1, y1] = [x0 + (x1 - x0) * ease, y0 + (y1 - y0) * ease];
        if (line.kind === 'negative') {
          ctx.setLineDash([2, 6]);
          ctx.strokeStyle = C.bad;
          ctx.globalAlpha = 0.8;
          ctx.lineWidth = 1.2;
        } else if (line.kind === 'neighbor') {
          ctx.strokeStyle = C.violetText;
          ctx.globalAlpha = 0.5;
          ctx.lineWidth = 1;
        } else {
          const grad = ctx.createLinearGradient(x0, y0, x1, y1);
          grad.addColorStop(0, C.starlight);
          grad.addColorStop(1, C.gold);
          ctx.strokeStyle = grad;
          ctx.globalAlpha = 0.9;
          ctx.lineWidth = 1 + 3.5 * line.share;
        }
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.stroke();
        ctx.setLineDash([]);
        if (!still && progress >= 1 && line.kind === 'reason') {
          ctx.globalCompositeOperation = 'lighter';
          const count = Math.ceil(2 + 8 * line.share);
          const len = Math.hypot(x1 - x0, y1 - y0);
          for (let p = 0; p < count; p++) {
            const t = (time / (1000 + len * 4) + p / count) % 1;
            drawGlow(ctx, C.gold, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, 1.4 + line.share * 2, Math.sin(Math.PI * t));
          }
          ctx.globalCompositeOperation = 'source-over';
        }
      }
    }
    ctx.globalAlpha = 1;

    // Shockwaves.
    ctx.globalCompositeOperation = 'lighter';
    rings = rings.filter((r) => time - r.t0 < r.dur);
    for (const r of rings) {
      const t = (time - r.t0) / r.dur;
      if (t < 0) continue;
      const [x, y] = toScreen(r.x, r.y);
      const e = 1 - (1 - t) ** 3;
      ctx.strokeStyle = r.color;
      ctx.globalAlpha = (1 - t) ** 1.6 * 0.9;
      ctx.lineWidth = r.w * (1 - t * 0.7);
      ctx.beginPath();
      ctx.ellipse(x, y, r.r * e, r.r * e * 0.92, 0, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Your games: white stars with diffraction spikes.
    for (const j of scene.history) {
      const [x, y] = toScreen(games[j].x, games[j].y);
      const tw = still ? 1 : 0.9 + 0.1 * Math.sin(time * 0.002 + phases[j]);
      drawGlow(ctx, '#ffffff', x, y, 4.2, 1);
      drawGlow(ctx, C.goldBright, x, y, 7, 0.35 * tw);
      drawSpikes(ctx, C.starlight, x, y, 22 * tw, 0.75);
    }

    // Picks: coloured by closeness, ringed in gold; the selected one pulses.
    scene.picks.forEach((i, rank) => {
      if (hidden.has(i)) return;
      const [x, y] = toScreen(games[i].x, games[i].y);
      const c = close ? close[i] : 1;
      const color = close ? closenessColor(c) : C.gold;
      const selected = scene.selected === i;
      const crater = craters.get(i);
      const cAge = crater !== undefined ? (time - crater) / 1000 : 9;
      const boom = cAge < 1.4 ? (1 - cAge / 1.4) ** 2 : 0;
      const size = (rank === 0 ? 6 : rank < 3 ? 5 : 4.2) * (selected ? 1.25 : 1);
      if (boom > 0) drawGlow(ctx, C.goldBright, x, y, size * (2 + 6 * boom), boom);
      const pulse = selected && !still ? (Math.sin(time / 420) + 1) / 2 : 0;
      drawGlow(ctx, color, x, y, size * (1.6 + pulse * 0.5), selected ? 0.55 + pulse * 0.25 : 0.4);
      drawGlow(ctx, '#ffffff', x, y, size * 0.7, 1);
      drawSpikes(ctx, color, x, y, size * (rank === 0 ? 6 : 4.2), selected ? 0.9 : 0.55);
      ctx.globalCompositeOperation = 'source-over';
      ctx.strokeStyle = C.gold;
      ctx.lineWidth = selected ? 1.6 : 1;
      ctx.globalAlpha = selected ? 0.95 : 0.55;
      const ringR = size * 2.4 + (selected ? 3 : 0);
      if (selected && !still) {
        const rot = time / 1600;
        for (let k = 0; k < 4; k++) {
          ctx.beginPath();
          ctx.arc(x, y, ringR + 4, rot + (k * Math.PI) / 2, rot + (k * Math.PI) / 2 + 0.9);
          ctx.stroke();
        }
      } else {
        ctx.beginPath();
        ctx.arc(x, y, ringR, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.globalCompositeOperation = 'lighter';
    });

    // Falling stars: lock-on beam, reticle, streak.
    for (const f of falls) {
      if (f.landed || time < f.spawn) continue;
      const g = games[f.game];
      const [tx, ty] = toScreen(g.x, g.y);
      const hang = f.rank === 0 ? 420 : 0;
      const fallStart = f.spawn + hang;
      const lockT = Math.min(1, (time - f.spawn) / Math.max(1, f.impact - f.spawn));
      // Beam from the top of the sky to the target.
      const beamA = 0.2 + 0.35 * f.strength * Math.min(1, lockT * 2);
      const bw = 2 + 8 * f.strength;
      const grad = ctx.createLinearGradient(tx, 0, tx, ty);
      grad.addColorStop(0, `${C.gold}00`);
      grad.addColorStop(1, C.gold);
      ctx.globalAlpha = beamA;
      ctx.fillStyle = grad;
      ctx.fillRect(tx - bw / 2, 0, bw, ty);
      // Reticle closing in.
      ctx.strokeStyle = C.goldBright;
      ctx.globalAlpha = 0.9;
      ctx.lineWidth = 1.4;
      const rr = 10 + 38 * (1 - lockT) * (0.6 + f.strength);
      const rot = lockT * Math.PI;
      for (let k = 0; k < 4; k++) {
        ctx.beginPath();
        ctx.arc(tx, ty, rr, rot + (k * Math.PI) / 2 + 0.25, rot + (k * Math.PI) / 2 + 1.25);
        ctx.stroke();
      }
      if (time < fallStart) continue;
      // The streak: from the upper right, accelerating.
      const L = ty + 160;
      const sx0 = tx + 0.42 * L;
      const sy0 = ty - L;
      const dur = f.impact - fallStart;
      const pos = (u: number): [number, number] => {
        const e = Math.max(0, u) ** 2.1;
        return [sx0 + (tx - sx0) * e, sy0 + (ty - sy0) * e];
      };
      const u = (time - fallStart) / dur;
      const steps = 16;
      const headW = 2.5 + 6 * f.strength;
      for (let k = steps; k >= 1; k--) {
        const [ax, ay] = pos(u - (k * 0.24) / steps);
        const [bx, by] = pos(u - ((k - 1) * 0.24) / steps);
        const fade = 1 - k / (steps + 1);
        ctx.strokeStyle = k > steps * 0.55 ? C.violet : C.gold;
        ctx.globalAlpha = fade ** 1.4 * 0.95;
        ctx.lineWidth = headW * fade;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        ctx.stroke();
      }
      const [hx, hy] = pos(u);
      drawGlow(ctx, C.goldBright, hx, hy, headW * 1.8, 1);
      drawGlow(ctx, '#ffffff', hx, hy, headW * 0.8, 1);
      drawSpikes(ctx, C.goldBright, hx, hy, headW * 6, 0.8);
    }

    // Embers.
    embers = embers.filter((e) => time - e.t0 < e.life);
    for (const e of embers) {
      const t = (time - e.t0) / 1000;
      const drag = Math.exp(-t * 1.8);
      const x = e.x + e.vx * (1 - drag) / 1.8 + shake.x;
      const y = e.y + (e.vy * (1 - drag)) / 1.8 + 260 * t * t + shake.y;
      const a = 1 - (time - e.t0) / e.life;
      drawGlow(ctx, e.color, x, y, e.size, a);
    }
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 1;

    // Labels by priority: the selected pick, your games, hubs, pick ranks, then bright stars.
    placed = [];
    if (scene.selected !== null && !hidden.has(scene.selected)) {
      const [x, y] = toScreen(games[scene.selected].x, games[scene.selected].y);
      label(ctx, games[scene.selected].title, x, y - 24, C.goldBright, { force: true, display: true, size: 17 });
    }
    for (const j of scene.history) {
      const [x, y] = toScreen(games[j].x, games[j].y);
      label(ctx, games[j].title, x, y + 26, C.starlight, { force: true });
    }
    for (const node of falls.length ? [] : scene.hubs.slice(0, 8)) {
      const h = hubAt(node);
      if (!h) continue;
      const [x, y] = toScreen(h.x, h.y);
      label(ctx, h.name, x, y - 11, C.violetText);
    }
    scene.picks.forEach((i, rank) => {
      if (scene.selected === i || hidden.has(i)) return;
      const [x, y] = toScreen(games[i].x, games[i].y);
      label(ctx, String(rank + 1), x + 16, y - 10, C.gold, { size: 13 });
    });
    // Exploring: when you zoom in on Discover, the brightest stars in view say what they are.
    if (app.view === 'discover' && cam.zoom > 1.8 && !scene.picks.length) {
      let shown = 0;
      for (const i of byPlays) {
        if (owned.has(i) || shown >= 18) continue;
        const [x, y] = toScreen(games[i].x, games[i].y);
        if (x < stage.x || y < stage.y || x > stage.x + stage.w || y > stage.y + stage.h) continue;
        const before = placed.length;
        label(ctx, games[i].title, x, y + 16, C.dust, { size: 11.5, alpha: 0.85 });
        if (placed.length > before) shown++;
      }
    }
    if (hovered !== null && !owned.has(hovered)) {
      const [x, y] = toScreen(games[hovered].x, games[hovered].y);
      ctx.strokeStyle = C.goldBright;
      ctx.lineWidth = 1.5;
      ctx.globalAlpha = 0.9;
      ctx.beginPath();
      ctx.arc(x, y, 9, 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    drawFlashes(time);

    // Keep keyboard markers and the inspect card on their stars.
    for (const el of markers.querySelectorAll<HTMLElement>('[data-game]')) {
      const g = games[Number(el.dataset.game)];
      const [x, y] = toScreen(g.x, g.y);
      el.style.transform = `translate(${x - 12}px, ${y - 12}px)`;
    }
    const anchor = document.querySelector<HTMLElement>('[data-anchor-game]');
    if (anchor) {
      const g = games[Number(anchor.dataset.anchorGame)];
      const [x, y] = toScreen(g.x, g.y);
      anchor.style.transform = `translate(${Math.round(x + 16)}px, ${Math.round(y - 16)}px)`;
    }
  }

  /** Impact frames: two frames of inverted light with speed lines converging on the impact. */
  function drawFlashes(time: number): void {
    const ctx = overlay.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    flashes = flashes.filter((f) => time - f.t0 < 280);
    if (app.reducedMotion) return;
    const diag = Math.hypot(width, height);
    for (const f of flashes) {
      const age = time - f.t0;
      const wedgeColor = (fg: string, alpha: number) => {
        ctx.fillStyle = fg;
        ctx.globalAlpha = alpha;
        ctx.beginPath();
        for (const [a, w, inner] of f.wedges) {
          // Lines rush inward: the inner tips close in on the impact across the frame.
          const r0 = diag * Math.max(0.02, inner + 0.04 * (1 - f.strength) - Math.min(age, 110) / 2200);
          ctx.moveTo(f.x + Math.cos(a) * r0, f.y + Math.sin(a) * r0);
          ctx.lineTo(f.x + Math.cos(a - w * 2.6) * diag, f.y + Math.sin(a - w * 2.6) * diag);
          ctx.lineTo(f.x + Math.cos(a + w * 2.6) * diag, f.y + Math.sin(a + w * 2.6) * diag);
          ctx.closePath();
        }
        ctx.fill();
      };
      if (f.full && age < 55) {
        ctx.globalAlpha = 0.93;
        ctx.fillStyle = C.starlight;
        ctx.fillRect(0, 0, width, height);
        wedgeColor(C.midnight, 1);
        ctx.globalAlpha = 1;
        ctx.fillStyle = C.midnight;
        ctx.beginPath();
        ctx.arc(f.x, f.y, 10 + 22 * f.strength, 0, Math.PI * 2);
        ctx.fill();
      } else if (f.full && age < 110) {
        ctx.globalAlpha = 0.9;
        ctx.fillStyle = C.midnight;
        ctx.fillRect(0, 0, width, height);
        wedgeColor(C.goldBright, 0.95);
        ctx.globalAlpha = 1;
        ctx.fillStyle = C.starlight;
        ctx.beginPath();
        ctx.arc(f.x, f.y, 14 + 30 * f.strength, 0, Math.PI * 2);
        ctx.fill();
      } else {
        const t = f.full ? (age - 110) / 170 : age / 280;
        wedgeColor(C.goldBright, (1 - t) * (f.full ? 0.35 : 0.3));
        const r = 40 + 220 * f.strength * (0.6 + t);
        const grad = ctx.createRadialGradient(f.x, f.y, 0, f.x, f.y, r);
        grad.addColorStop(0, C.goldBright);
        grad.addColorStop(1, `${C.gold}00`);
        ctx.globalAlpha = (1 - t) * 0.55;
        ctx.fillStyle = grad;
        ctx.fillRect(f.x - r, f.y - r, r * 2, r * 2);
      }
    }
    ctx.globalAlpha = 1;
  }

  // ---------- loop ----------
  function busy(time: number): boolean {
    return (
      falls.length > 0 ||
      rings.length > 0 ||
      embers.length > 0 ||
      flashes.length > 0 ||
      time - shakeStart < 600 ||
      (ripple !== null && time - ripple.t0 < 4200) ||
      time - drawStart < 750
    );
  }

  function loop(time: number): void {
    const dt = Math.min(0.05, last ? (time - last) / 1000 : 0.016);
    last = time;
    const moving = step(dt);
    if (falls.length) updateFalls(time);
    draw(time);
    raf = 0;
    if (document.hidden) return;
    const flowing = !app.reducedMotion && (app.scene.lines.length > 0 || app.scene.selected !== null);
    if (moving || busy(time) || flowing) raf = requestAnimationFrame(loop);
    else if (!app.reducedMotion) idle = setTimeout(() => ((idle = 0), (raf = requestAnimationFrame(loop))), 50);
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
    for (const c of [canvas, overlay]) {
      c.width = Math.round(width * dpr);
      c.height = Math.round(height * dpr);
      c.style.width = `${width}px`;
      c.style.height = `${height}px`;
    }
    buildNebula();
    measureStage();
    wake();
  }

  function nearest(sx: number, sy: number): number | null {
    const games = app.slice?.games;
    if (!games) return null;
    let best: number | null = null;
    let bestD = 16 * 16;
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
    sfx.unlock();
    if (falls.length) {
      finishFall(performance.now());
      wake();
      return;
    }
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
    if (drag && !drag.moved) app.inspect = nearest(e.clientX, e.clientY);
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

  $effect(() => {
    const scene = app.scene;
    const now = performance.now();
    if (scene.key !== sceneKey) {
      sceneKey = scene.key;
      drawStart = now;
      measureStage();
      if (!userMoved || scene.focus.length) {
        userMoved = false;
        frame(scene);
      }
    }
    // A new game in your sky: a soft violet ring where it lit up.
    const games = app.slice?.games;
    if (games) {
      for (const j of scene.history) {
        if (!prevHistory.has(j) && scene.picks.length === 0) {
          rings.push({ x: games[j].x, y: games[j].y, t0: now, dur: 900, r: 70, color: C.violetText, w: 1.5 });
        }
      }
      prevHistory = new Set(scene.history);
    }
    const fall = scene.fall ?? null;
    if (fall !== fallKey) {
      fallKey = fall;
      if (fall && scene.picks.length) {
        fallSeed = scene.picks.reduce((s, p) => (s * 31 + p + 1) % 2147483647, 7) || 1;
        if (app.reducedMotion || app.view !== 'discover') finishFall(now);
        else startFall(scene, now);
      } else {
        falls = [];
        app.falling = false;
        app.landed = scene.picks.length;
        ripple = null;
      }
    }
    if (scene.closeness && !ripple && !falls.length) startRipple(now - 5000);
    if (!scene.closeness) ripple = null;
    wake();
  });

  $effect(() => {
    void app.skipFall;
    if (falls.length) finishFall(performance.now());
  });

  $effect(() => {
    if (app.view !== 'discover' && falls.length) finishFall(performance.now());
  });

  $effect(() => {
    void settings.palette;
    wake();
  });

  $effect(() => {
    void app.view;
    void app.history.length;
    void app.result;
    void app.landed;
    requestAnimationFrame(() => {
      measureStage();
      wake();
    });
  });

  $effect(() => {
    const games = app.slice?.games;
    if (games) {
      maxPlays = Math.max(...games.map((g) => g.plays));
      byPlays = games.map((_, i) => i).sort((a, b) => games[b].plays - games[a].plays);
      phases = new Float32Array(games.length).map((_, i) => ((i * 2654435761) % 1000) / 159.15);
    }
    wake();
  });

  onMount(() => {
    const fonts = getComputedStyle(document.documentElement);
    bodyFont = fonts.getPropertyValue('--font-body') || bodyFont;
    displayFont = fonts.getPropertyValue('--font-display') || displayFont;
    resize();
    const ro = new ResizeObserver(() => {
      measureStage();
      wake();
    });
    ro.observe(document.body);
    const onVisible = () => {
      // Coming back to a half-finished fall would land every star at once: finish it while hidden.
      if (document.hidden && falls.length) finishFall(performance.now());
      wake();
    };
    const onKey = (e: KeyboardEvent) => {
      sfx.unlock();
      if (falls.length && (e.key === 'Escape' || e.key === ' ' || e.key === 'Enter')) finishFall(performance.now());
    };
    const onFirst = () => sfx.unlock();
    window.addEventListener('resize', resize);
    window.addEventListener('keydown', onKey);
    window.addEventListener('pointerdown', onFirst, { capture: true });
    document.addEventListener('visibilitychange', onVisible);
    canvas.addEventListener('wheel', onWheel, { passive: false });
    document.fonts?.ready.then(() => wake());
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', resize);
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('pointerdown', onFirst, { capture: true });
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
<canvas bind:this={overlay} class="impact" aria-hidden="true"></canvas>

<div class="markers" bind:this={markers}>
  {#if app.slice}
    {#each app.scene.picks as i, rank (i)}
      {#if rank >= app.scene.picks.length - app.landed}
        <button
          class="marker"
          data-game={i}
          aria-label={`Pick ${rank + 1}: ${app.slice.games[i].title}`}
          aria-pressed={app.scene.selected === i}
          onclick={() => {
            app.selected = rank;
            sfx.select();
          }}
        ></button>
      {/if}
    {/each}
  {/if}
</div>

{#if tooltip && hovered !== null && app.slice && !app.falling}
  <div class="tooltip" style:left={`${tooltip.x + 16}px`} style:top={`${tooltip.y + 14}px`} aria-hidden="true">
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
  .impact {
    position: fixed;
    inset: 0;
    z-index: 40;
    pointer-events: none;
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
    width: 24px;
    height: 24px;
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
    background: var(--surface-solid);
    color: var(--text);
    border: var(--border);
    border-radius: var(--radius-sm);
    padding: 4px 10px;
    font-size: var(--text-sm);
    font-weight: 500;
  }
</style>
