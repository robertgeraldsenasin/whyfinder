/**
 * history → s = x·M → drop owned, filters → top 100 → DPP → top 10.
 * Twin of src/whyfinder/rerank/pipeline.py; counterfactual search re-runs exactly this.
 */
import { score } from './blend';
import { type DppStep, greedyMap, type SparseVector } from './dpp';
import type { HistoryEntry } from './types';

export interface Recommendation {
  scores: Float64Array;
  candidates: number[];
  relevanceTop: number[];
  picks: number[];
  variety: boolean[];
  steps: DppStep[];
}

export function rankCandidates(
  scores: Float64Array,
  gameIds: number[],
  excluded: Set<number>,
  allowed: boolean[] | null,
  n: number,
): number[] {
  const pool: number[] = [];
  for (let i = 0; i < scores.length; i++) if (!excluded.has(i) && (!allowed || allowed[i])) pool.push(i);
  pool.sort((a, b) => (scores[a] !== scores[b] ? (scores[b] > scores[a] ? 1 : -1) : gameIds[a] - gameIds[b]));
  return pool.slice(0, n);
}

export interface PipelineOptions {
  vectors: SparseVector[];
  gameIds: number[];
  k: number;
  nCandidates: number;
  theta: number;
  allowed?: boolean[] | null;
}

/** `row(j)` returns M's row for catalogue game j. */
export function recommend(
  history: HistoryEntry[],
  row: (j: number) => Float64Array,
  n: number,
  options: PipelineOptions,
): Recommendation {
  if (history.length === 0) throw new Error('history is empty');
  const s = score(
    history.map(([, x]) => x),
    history.map(([j]) => row(j)),
    n,
  );
  const owned = new Set(history.map(([j]) => j));
  const candidates = rankCandidates(s, options.gameIds, owned, options.allowed ?? null, options.nCandidates);
  const { picks, steps } = greedyMap(
    candidates,
    candidates.map((i) => s[i]),
    options.vectors,
    options.gameIds,
    options.k,
    options.theta,
  );
  const relevanceTop = candidates.slice(0, options.k);
  const top = new Set(relevanceTop);
  return { scores: s, candidates, relevanceTop, picks, variety: picks.map((p) => !top.has(p)), steps };
}
