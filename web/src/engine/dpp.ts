/**
 * DPP re-ranking by greedy MAP with incremental Cholesky (Chen, Zhang & Zhou, NeurIPS 2018).
 * Twin of src/whyfinder/rerank/dpp.py.
 */
import { byCodePoint } from './graph';

export type SparseVector = [feature: number, value: number][];
const MIN_GAIN = 1e-12;

/** Binary TF-IDF over sorted vocabulary, idf(t) = ln(1 + n/df(t)), L2-normalised. */
export function tfidfVectors(features: string[][]): SparseVector[] {
  const df = new Map<string, number>();
  for (const items of features) for (const f of new Set(items)) df.set(f, (df.get(f) ?? 0) + 1);
  const vocabulary = new Map([...df.keys()].sort(byCodePoint).map((f, k) => [f, k]));
  const n = features.length;
  const idf = new Map([...df].map(([f, c]) => [f, Math.log(1 + n / c)]));
  return features.map((items) => {
    const entries: SparseVector = [...new Set(items)].map((f) => [vocabulary.get(f)!, idf.get(f)!]);
    entries.sort((a, b) => a[0] - b[0]);
    let total = 0;
    for (const [, v] of entries) total += v * v;
    const norm = Math.sqrt(total);
    return norm > 0 ? entries.map(([k, v]) => [k, v / norm]) : [];
  });
}

export function similarity(a: SparseVector, b: SparseVector): number {
  let i = 0;
  let j = 0;
  let total = 0;
  while (i < a.length && j < b.length) {
    if (a[i][0] === b[j][0]) {
      total += a[i][1] * b[j][1];
      i++;
      j++;
    } else if (a[i][0] < b[j][0]) i++;
    else j++;
  }
  return total;
}

export function rescale(scores: number[]): number[] {
  const lo = Math.min(...scores);
  const hi = Math.max(...scores);
  if (!(hi > lo)) return scores.map(() => 1);
  return scores.map((s) => (s - lo) / (hi - lo));
}

export interface DppStep {
  picked: number;
  gain: number;
  /** d² of every candidate still in play before this pick: [catalogue index, d²]. */
  gains: [number, number][];
}

export function greedyMap(
  candidates: number[],
  scores: number[],
  vectors: SparseVector[],
  gameIds: number[],
  k: number,
  theta: number,
): { picks: number[]; steps: DppStep[] } {
  if (k < 1) throw new Error('k must be at least 1');
  if (candidates.length !== scores.length) throw new Error('candidates and scores differ in length');
  const quality = candidates.length ? rescale(scores).map((s) => Math.exp(theta * s)) : [];
  const q = new Map(candidates.map((c, t) => [c, quality[t]]));
  const d2 = new Map(candidates.map((c) => [c, q.get(c)! * 1 * q.get(c)!]));
  const rows = new Map<number, number[]>(candidates.map((c) => [c, []]));
  const remaining = [...candidates];
  const picks: number[] = [];
  const steps: DppStep[] = [];
  while (remaining.length && picks.length < k) {
    let j = remaining[0];
    for (const i of remaining.slice(1)) {
      const di = d2.get(i)!;
      const dj = d2.get(j)!;
      if (di > dj || (di === dj && gameIds[i] < gameIds[j])) j = i;
    }
    if (d2.get(j)! < MIN_GAIN) break;
    steps.push({ picked: j, gain: d2.get(j)!, gains: remaining.map((i) => [i, d2.get(i)!]) });
    picks.push(j);
    remaining.splice(remaining.indexOf(j), 1);
    const dj = Math.sqrt(d2.get(j)!);
    const cj = rows.get(j)!;
    for (const i of remaining) {
      const ci = rows.get(i)!;
      let dot = 0;
      for (let t = 0; t < cj.length; t++) dot += cj[t] * ci[t];
      const Lji = q.get(j)! * similarity(vectors[j], vectors[i]) * q.get(i)!;
      const e = (Lji - dot) / dj;
      ci.push(e);
      d2.set(i, d2.get(i)! - e * e);
    }
  }
  for (const i of candidates) {
    if (picks.length >= k) break;
    if (!picks.includes(i)) picks.push(i);
  }
  return { picks, steps };
}
