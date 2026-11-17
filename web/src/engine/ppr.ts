/**
 * Personalized PageRank by forward push in synchronous rounds (Andersen, Chung & Lang 2006).
 * Twin of src/whyfinder/graph/ppr.py: same thresholds, same round structure, same summation order.
 * Guarantee: |π(v) − p(v)| ≤ ε·d(v). A node with no edges keeps its whole residual.
 */
import type { Graph } from './graph';

export interface PushRound {
  /** Nodes that pushed this round (ascending). */
  active: Int32Array;
  /** The estimate p after this round, for the live picture. */
  p: Float32Array;
  settled: number;
  residual: number;
}

export interface PushResult {
  p: Float64Array;
  rounds: number;
  pushes: number;
  residualMass: number;
  trace?: PushRound[];
}

export function push(
  graph: Graph,
  seed: number,
  alpha: number,
  eps: number,
  options: { trace?: boolean } = {},
): PushResult {
  if (!(alpha > 0 && alpha < 1)) throw new Error('alpha must be in (0, 1)');
  if (!(eps > 0)) throw new Error('eps must be positive');
  const n = graph.kinds.length;
  if (!(seed >= 0 && seed < n)) throw new Error(`seed ${seed} is not a node`);
  const { degree, indptr, indices, weights } = graph;
  const threshold = new Float64Array(n);
  for (let v = 0; v < n; v++) threshold[v] = eps * degree[v];
  const p = new Float64Array(n);
  let r = new Float64Array(n);
  r[seed] = 1;
  let rounds = 0;
  let pushes = 0;
  const trace: PushRound[] | undefined = options.trace ? [] : undefined;
  const active: number[] = [];
  for (;;) {
    active.length = 0;
    for (let v = 0; v < n; v++) if (r[v] > threshold[v]) active.push(v);
    if (active.length === 0) break;
    rounds++;
    pushes += active.length;
    for (const v of active) p[v] = p[v] + (degree[v] > 0 ? alpha : 1) * r[v];
    const acc = new Float64Array(n);
    for (const v of active) {
      if (!(degree[v] > 0)) continue;
      const f = ((1 - alpha) * r[v]) / degree[v];
      for (let e = indptr[v]; e < indptr[v + 1]; e++) acc[indices[e]] += f * weights[e];
    }
    const next = new Float64Array(n);
    let k = 0;
    for (let u = 0; u < n; u++) {
      const kept = k < active.length && active[k] === u ? (k++, 0) : r[u];
      next[u] = kept + acc[u];
    }
    r = next;
    if (trace) {
      let settled = 0;
      let residual = 0;
      for (let u = 0; u < n; u++) {
        settled += p[u];
        residual += r[u];
      }
      trace.push({ active: Int32Array.from(active), p: Float32Array.from(p), settled, residual });
    }
  }
  let residualMass = 0;
  for (let u = 0; u < n; u++) residualMass += r[u];
  return { p, rounds, pushes, residualMass, trace };
}

/** Keep the m largest positive entries (ties by index). */
export function keepTop(row: Float64Array, m: number): Float64Array {
  const order = Array.from(row.keys());
  order.sort((a, b) => (row[a] !== row[b] ? (row[b] > row[a] ? 1 : -1) : a - b));
  const out = new Float64Array(row.length);
  for (const i of order.slice(0, m)) if (row[i] > 0) out[i] = row[i];
  return out;
}

/** Row `seed` of Π: the top m game entries of p, seed excluded. */
export function piRow(graph: Graph, seed: number, alpha: number, eps: number, topM: number): Float64Array {
  const p = push(graph, seed, alpha, eps).p.slice(0, graph.nGames);
  p[seed] = 0;
  return keepTop(p, topM);
}
