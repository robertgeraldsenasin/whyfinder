/** App state (Svelte 5 runes). One instance, imported by every view. */
import type { Explained } from '../engine/engine';
import type { Progress, ReadyInfo } from '../engine/protocol';
import type { ModelFile, Slice } from '../engine/types';
import { EngineClient } from './engine-client';
import type { Evidence } from './evidence';
import { settings } from './settings.svelte';

export type View = 'discover' | 'hood' | 'architecture';

export interface SceneLine {
  from: number;
  to: number;
  share: number;
  kind: 'reason' | 'negative' | 'neighbor' | 'related';
  hub?: number;
}

/** What the atlas draws. Views set it; the atlas animates between scenes. */
export interface Scene {
  focus: number[];
  history: number[];
  picks: number[];
  selected: number | null;
  lines: SceneLine[];
  glow: Float32Array | null;
  hubs: number[];
  hubGlow: Map<number, number> | null;
  dim: number;
  key: string;
  /** Closeness of every game to your taste (NaN for yours); colours the whole sky. */
  closeness?: Float32Array | null;
  /** When this changes, the picks fall from the sky instead of appearing. */
  fall?: string | null;
}

export const emptyScene = (): Scene => ({
  focus: [],
  history: [],
  picks: [],
  selected: null,
  lines: [],
  glow: null,
  hubs: [],
  hubGlow: null,
  dim: 0,
  key: 'empty',
});

export interface HistoryItem {
  index: number;
  hours: number;
}

export function viewFromHash(hash: string): View {
  if (hash.startsWith('#/hood')) return 'hood';
  if (hash.startsWith('#/architecture')) return 'architecture';
  return 'discover';
}

class AppState {
  view = $state<View>('discover');
  reducedMotion = $state(false);
  slice = $state.raw<Slice | null>(null);
  model = $state.raw<ModelFile | null>(null);
  ready = $state.raw<ReadyInfo | null>(null);
  progress = $state.raw<Progress | null>(null);
  error = $state<string | null>(null);
  history = $state<HistoryItem[]>([]);
  result = $state.raw<Explained | null>(null);
  resultFor = $state('');
  running = $state(false);
  selected = $state(0);
  inspect = $state<number | null>(null);
  beta = $state(0.5);
  theta = $state(2);
  stage = $state(0);
  scene = $state.raw<Scene>(emptyScene());
  /** How many picks have landed in the current starfall (all of them when it is over). */
  landed = $state(0);
  falling = $state(false);
  /** Ask the atlas to finish the starfall at once. */
  skipFall = $state(0);
  evidence = $state.raw<Evidence | null>(null);
  verified = $state.raw<{ cB: number; cPi: number; seconds: number; cBModel: number; cPiModel: number } | null>(null);
  client: EngineClient | null = null;

  get historyKey(): string {
    return this.history.map((h) => `${h.index}:${h.hours}`).join(',') + `|${this.beta}|${this.theta}`;
  }

  get stale(): boolean {
    return this.result !== null && this.resultFor !== this.historyKey;
  }

  go(view: View): void {
    const hash = view === 'discover' ? '#/' : `#/${view}`;
    if (location.hash !== hash) history.pushState(null, '', hash);
    this.view = view;
  }

  async load(base: string): Promise<void> {
    settings.load();
    try {
      const [slice, model] = await Promise.all([
        fetch(`${base}data/demo-slice.json`).then((r) => r.json() as Promise<Slice>),
        fetch(`${base}data/model.json`).then((r) => r.json() as Promise<ModelFile>),
      ]);
      this.slice = slice;
      this.model = model;
      this.beta = model.params.beta;
      this.theta = model.params.theta;
      this.client = new EngineClient();
      this.ready = await this.client.init(slice, model, (p) => (this.progress = p));
      this.progress = null;
      // Review evidence is optional: the demo works without it.
      fetch(`${base}data/reviews.json`)
        .then((r) => (r.ok ? (r.json() as Promise<Evidence>) : null))
        .then((ev) => (this.evidence = ev))
        .catch(() => (this.evidence = null));
    } catch (error) {
      this.error = error instanceof Error ? error.message : String(error);
    }
  }

  add(index: number, hours = 20): void {
    if (this.history.some((h) => h.index === index) || this.history.length >= 12) return;
    this.history = [...this.history, { index, hours }];
  }

  remove(index: number): void {
    this.history = this.history.filter((h) => h.index !== index);
    if (this.history.length === 0) this.result = null;
  }

  setHours(index: number, hours: number): void {
    this.history = this.history.map((h) => (h.index === index ? { ...h, hours } : h));
  }

  async find(): Promise<void> {
    if (!this.client || this.history.length === 0) return;
    this.running = true;
    const key = this.historyKey;
    try {
      const result = await this.client.explain(
        this.history.map((h) => [h.index, h.hours]),
        this.beta,
        this.theta,
      );
      const sameGames = this.resultFor.split('|')[0] === key.split('|')[0];
      this.result = result;
      this.resultFor = key;
      this.selected = sameGames ? Math.min(this.selected, result.picks.length - 1) : 0;
    } catch (error) {
      this.error = error instanceof Error ? error.message : String(error);
    } finally {
      this.running = false;
    }
  }

  async verify(): Promise<void> {
    if (!this.client || this.verified) return;
    this.verified = await this.client.verify((p) => (this.progress = p));
    this.progress = null;
  }
}

export const app = new AppState();
