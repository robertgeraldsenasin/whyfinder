/** Shapes shared by the engine, the worker and the UI. */

export interface SliceGame {
  id: number;
  title: string;
  developer: string | null;
  publisher: string | null;
  tags: string[];
  genres: string[];
  year: number | null;
  price: number | null;
  plays: number;
  x: number;
  y: number;
}

/** `whyfinder export demo`: aggregates only (ADR-0015). */
export interface Slice {
  version: number;
  source: string;
  split: { t1: string | null; method: string | null };
  users: number;
  games: SliceGame[];
  gram: { n: number; packed_upper: number[] };
}

/** Every tunable, exported from params.yaml by `whyfinder export model`, so both engines agree. */
export interface Params {
  lambda: number;
  restartAlpha: number;
  pushEps: number;
  topM: number;
  tagsPerGame: number;
  coplayPerGame: number;
  weights: { tag: number; developer: number; publisher: number; coplay: number };
  beta: number;
  topKPerRow: number;
  candidates: number;
  theta: number;
  k: number;
  confidence: { alpha: number; eps: number };
}

/** `whyfinder export model`: parameters and the constants that need the whole slice. */
export interface ModelFile {
  version: number;
  params: Params;
  cB: number;
  cPi: number;
  build: {
    easeSeconds: number;
    piSeconds: number;
    graphNodes: number;
    graphEdges: number;
    piTruncationLoss: { mean: number; max: number };
  };
}

/** One entry of the history: catalogue index and confidence weight x. */
export type HistoryEntry = [index: number, weight: number];
