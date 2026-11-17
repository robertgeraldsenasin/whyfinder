/** App state (Svelte 5 runes). One instance, imported by every view. */
import type { Explained } from '../engine/engine';
import type { Progress, ReadyInfo } from '../engine/protocol';
import type { ModelFile, Slice } from '../engine/types';
import { EngineClient } from './engine-client';

export type View = 'discover' | 'hood' | 'architecture';
export type Theme = 'deep-field' | 'atlas-paper';

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

const THEME_KEY = 'whyfinder.theme';

function readTheme(): Theme {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === 'deep-field' || saved === 'atlas-paper') return saved;
  } catch {
    /* storage can be unavailable */
  }
  return typeof matchMedia !== 'undefined' && matchMedia('(prefers-color-scheme: light)').matches
    ? 'atlas-paper'
    : 'deep-field';
}

export function viewFromHash(hash: string): View {
  if (hash.startsWith('#/hood')) return 'hood';
  if (hash.startsWith('#/architecture')) return 'architecture';
  return 'discover';
}

class AppState {
  view = $state<View>('discover');
  theme = $state<Theme>('deep-field');
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
  verified = $state.raw<{ cB: number; cPi: number; seconds: number; cBModel: number; cPiModel: number } | null>(null);
  client: EngineClient | null = null;

  get historyKey(): string {
    return this.history.map((h) => `${h.index}:${h.hours}`).join(',') + `|${this.beta}|${this.theta}`;
  }

  get stale(): boolean {
    return this.result !== null && this.resultFor !== this.historyKey;
  }

  setTheme(theme: Theme): void {
    this.theme = theme;
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* ignore */
    }
  }

  go(view: View): void {
    const hash = view === 'discover' ? '#/' : `#/${view}`;
    if (location.hash !== hash) history.pushState(null, '', hash);
    this.view = view;
  }

  async load(base: string): Promise<void> {
    this.setTheme(readTheme());
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
