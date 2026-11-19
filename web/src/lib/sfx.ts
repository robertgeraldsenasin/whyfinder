/**
 * Sound effects, synthesized with the Web Audio API (no audio files). The context starts on the
 * first click or key press, as browsers require; until then every call is silent.
 */
import { settings } from './settings.svelte';

type Ctx = AudioContext;

let ctx: Ctx | null = null;
let master: GainNode | null = null;
let noise: AudioBuffer | null = null;

/** Notes of a D major pentatonic, low to high; impacts climb down it so #1 lands on the root. */
const PENTA = [293.66, 329.63, 369.99, 440, 493.88, 587.33, 659.25, 739.99, 880, 987.77];

function audio(): Ctx | null {
  if (!settings.sound || typeof window === 'undefined') return null;
  if (!ctx) return null;
  if (ctx.state === 'suspended') void ctx.resume();
  if (master) master.gain.value = settings.volume * 0.7;
  return ctx;
}

/** Call from a user gesture. */
export function unlock(): void {
  if (ctx || typeof window === 'undefined') return;
  const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return;
  ctx = new Ctor();
  const comp = ctx.createDynamicsCompressor();
  comp.threshold.value = -14;
  comp.ratio.value = 4;
  master = ctx.createGain();
  master.gain.value = settings.volume * 0.7;
  master.connect(comp).connect(ctx.destination);
  noise = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
  const data = noise.getChannelData(0);
  let seed = 7;
  for (let i = 0; i < data.length; i++) {
    seed = (seed * 16807) % 2147483647;
    data[i] = (seed / 2147483647) * 2 - 1;
  }
}

function env(c: Ctx, at: number, peak: number, attack: number, decay: number): GainNode {
  const g = c.createGain();
  g.gain.setValueAtTime(0.0001, at);
  g.gain.exponentialRampToValueAtTime(peak, at + attack);
  g.gain.exponentialRampToValueAtTime(0.0001, at + attack + decay);
  return g;
}

function out(c: Ctx, pan: number): AudioNode {
  const p = c.createStereoPanner();
  p.pan.value = Math.max(-1, Math.min(1, pan));
  p.connect(master!);
  return p;
}

/** A falling star: filtered noise sweeping down, `duration` seconds long. */
export function whoosh(duration: number, pan = 0, strength = 0.5, delay = 0): void {
  const c = audio();
  if (!c || !noise) return;
  const at = c.currentTime + delay;
  const src = c.createBufferSource();
  src.buffer = noise;
  src.loop = true;
  const bp = c.createBiquadFilter();
  bp.type = 'bandpass';
  bp.Q.value = 1.4;
  bp.frequency.setValueAtTime(5200, at);
  bp.frequency.exponentialRampToValueAtTime(420, at + duration);
  const g = c.createGain();
  g.gain.setValueAtTime(0.0001, at);
  g.gain.exponentialRampToValueAtTime(0.32 * strength + 0.05, at + duration * 0.85);
  g.gain.exponentialRampToValueAtTime(0.0001, at + duration + 0.05);
  src.connect(bp).connect(g).connect(out(c, pan));
  src.start(at);
  src.stop(at + duration + 0.1);
}

/** A star striking: a low thump, a noise crack and a bell tuned by rank (0 is the best pick). */
export function impact(rank: number, pan = 0, strength = 0.5): void {
  const c = audio();
  if (!c || !noise) return;
  const at = c.currentTime;
  const dest = out(c, pan);

  const kick = c.createOscillator();
  kick.type = 'sine';
  kick.frequency.setValueAtTime(140 + 40 * strength, at);
  kick.frequency.exponentialRampToValueAtTime(38, at + 0.35);
  kick.connect(env(c, at, 0.55 * strength + 0.2, 0.004, 0.45 + 0.4 * strength)).connect(dest);
  kick.start(at);
  kick.stop(at + 1);

  const crack = c.createBufferSource();
  crack.buffer = noise;
  const lp = c.createBiquadFilter();
  lp.type = 'lowpass';
  lp.frequency.setValueAtTime(6000, at);
  lp.frequency.exponentialRampToValueAtTime(300, at + 0.4);
  crack.connect(lp).connect(env(c, at, 0.35 * strength + 0.08, 0.002, 0.35)).connect(dest);
  crack.start(at);
  crack.stop(at + 0.5);

  const f = PENTA[Math.min(PENTA.length - 1, Math.max(0, rank))] / (rank === 0 ? 2 : 1);
  const partials = rank === 0 ? [1, 1.5, 2, 2.76, 4] : [1, 2.76, 5.4];
  partials.forEach((ratio, k) => {
    const o = c.createOscillator();
    o.type = 'sine';
    o.frequency.value = f * ratio;
    o.connect(env(c, at + 0.01, (0.16 / (k + 1)) * (0.6 + strength), 0.006, (rank === 0 ? 2.6 : 1.3) / (1 + k * 0.4))).connect(dest);
    o.start(at);
    o.stop(at + 3);
  });
}

/** Locking on to where a star will fall: a quick rising glissando. */
export function lock(pan = 0): void {
  const c = audio();
  if (!c) return;
  const at = c.currentTime;
  const o = c.createOscillator();
  o.type = 'triangle';
  o.frequency.setValueAtTime(520, at);
  o.frequency.exponentialRampToValueAtTime(1560, at + 0.32);
  o.connect(env(c, at, 0.06, 0.03, 0.36)).connect(out(c, pan));
  o.start(at);
  o.stop(at + 0.5);
}

/** A card dealt off the deck: a short bright flick with a click at the front. */
export function deal(pan = 0, strength = 0.5): void {
  const c = audio();
  if (!c || !noise) return;
  const at = c.currentTime;
  const src = c.createBufferSource();
  src.buffer = noise;
  const hp = c.createBiquadFilter();
  hp.type = 'highpass';
  hp.frequency.setValueAtTime(2400, at);
  hp.frequency.exponentialRampToValueAtTime(5200, at + 0.07);
  src.connect(hp).connect(env(c, at, 0.18 + 0.12 * strength, 0.002, 0.08)).connect(out(c, pan));
  src.start(at);
  src.stop(at + 0.15);
  const click = c.createOscillator();
  click.type = 'square';
  click.frequency.setValueAtTime(1800, at);
  click.frequency.exponentialRampToValueAtTime(600, at + 0.03);
  click.connect(env(c, at, 0.04, 0.001, 0.03)).connect(out(c, pan));
  click.start(at);
  click.stop(at + 0.06);
}

/** The Ace lands: a short brass "ta-da", two chords a fourth apart, with a cymbal swell. */
export function tada(pan = 0): void {
  const c = audio();
  if (!c || !noise) return;
  const at = c.currentTime + 0.06;
  const dest = out(c, pan * 0.5);
  const chords: [number, number[], number][] = [
    [0, [293.66, 369.99, 440], 0.16],
    [0.16, [392, 493.88, 587.33, 783.99], 0.9],
  ];
  for (const [t, notes, len] of chords) {
    for (const f of notes) {
      const o = c.createOscillator();
      o.type = 'sawtooth';
      o.frequency.setValueAtTime(f * 0.985, at + t);
      o.frequency.exponentialRampToValueAtTime(f, at + t + 0.05);
      const lp = c.createBiquadFilter();
      lp.type = 'lowpass';
      lp.frequency.setValueAtTime(900, at + t);
      lp.frequency.exponentialRampToValueAtTime(2600, at + t + 0.06);
      lp.frequency.exponentialRampToValueAtTime(1200, at + t + len);
      o.connect(lp).connect(env(c, at + t, 0.045, 0.02, len)).connect(dest);
      o.start(at + t);
      o.stop(at + t + len + 0.2);
    }
  }
  const cym = c.createBufferSource();
  cym.buffer = noise;
  cym.loop = true;
  const hp = c.createBiquadFilter();
  hp.type = 'highpass';
  hp.frequency.value = 6500;
  cym.connect(hp).connect(env(c, at + 0.16, 0.09, 0.05, 1.1)).connect(dest);
  cym.start(at + 0.16);
  cym.stop(at + 1.5);
}

/** Choosing a pick: a card slid across the table, then a light chime. */
export function select(): void {
  const c = audio();
  if (!c) return;
  const at = c.currentTime;
  if (noise) {
    const src = c.createBufferSource();
    src.buffer = noise;
    const bp = c.createBiquadFilter();
    bp.type = 'bandpass';
    bp.Q.value = 0.8;
    bp.frequency.setValueAtTime(1800, at);
    bp.frequency.exponentialRampToValueAtTime(3600, at + 0.09);
    src.connect(bp).connect(env(c, at, 0.06, 0.01, 0.09)).connect(out(c, 0));
    src.start(at);
    src.stop(at + 0.14);
  }
  [880, 1318.5].forEach((f, k) => {
    const o = c.createOscillator();
    o.type = 'sine';
    o.frequency.value = f;
    o.connect(env(c, at + k * 0.06, 0.07, 0.005, 0.5)).connect(out(c, 0));
    o.start(at + k * 0.06);
    o.stop(at + 0.8);
  });
}

/** Adding one of your games: a three-note twinkle. */
export function twinkle(pan = 0): void {
  const c = audio();
  if (!c) return;
  const at = c.currentTime;
  [1760, 2217.5, 2637].forEach((f, k) => {
    const o = c.createOscillator();
    o.type = 'sine';
    o.frequency.value = f;
    o.connect(env(c, at + k * 0.05, 0.05, 0.004, 0.32)).connect(out(c, pan));
    o.start(at + k * 0.05);
    o.stop(at + 0.6);
  });
}
