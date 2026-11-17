/**
 * Exact attributions, counterfactuals and "related by" paths.
 * Twins of src/whyfinder/explain/{attributions,counterfactual,paths}.py.
 */
import type { Graph, NodeKind } from './graph';
import { neighbours } from './graph';
import type { HistoryEntry } from './types';

export interface Contribution {
  game: number;
  total: number;
  ease: number;
  ppr: number;
}

/** Contribution of each history game to `pick`, largest first (ties by game ID). */
export function attributions(
  history: HistoryEntry[],
  pick: number,
  mRow: (j: number) => Float64Array,
  bRow: (j: number) => ArrayLike<number>,
  piRow: (j: number) => ArrayLike<number>,
  beta: number,
  cB: number,
  cPi: number,
  gameIds: number[],
): Contribution[] {
  const out = history.map(([j, x]) => ({
    game: j,
    total: x * mRow(j)[pick],
    ease: x * (beta * (bRow(j)[pick] / cB)),
    ppr: x * ((1 - beta) * (piRow(j)[pick] / cPi)),
  }));
  return out.sort((a, b) => (a.total !== b.total ? (b.total > a.total ? 1 : -1) : gameIds[a.game] - gameIds[b.game]));
}

export type Pipeline = (history: HistoryEntry[]) => number[];
export type TrailStep = [action: 'remove' | 'prune', tried: number[], stillShown: boolean];

export interface Counterfactual {
  pick: number;
  removed: number[];
  runs: number;
  trail: TrailStep[];
}

function drops(pipeline: Pipeline, history: HistoryEntry[], removed: Set<number>, pick: number): boolean {
  const rest = history.filter(([j]) => !removed.has(j));
  return rest.length === 0 || !pipeline(rest).includes(pick);
}

/** Greedy removal in `order`, then pruning until irreducible (ADR-0012, live mode). */
export function greedyCounterfactual(
  pipeline: Pipeline,
  history: HistoryEntry[],
  pick: number,
  order: number[],
): Counterfactual {
  let removed: number[] = [];
  const trail: TrailStep[] = [];
  let runs = 0;
  for (const j of order) {
    removed.push(j);
    runs++;
    const dropped = drops(pipeline, history, new Set(removed), pick);
    trail.push(['remove', [...removed], !dropped]);
    if (dropped) break;
  }
  let changed = true;
  while (changed && removed.length > 1) {
    changed = false;
    for (const j of [...removed]) {
      const trial = removed.filter((g) => g !== j);
      runs++;
      const dropped = drops(pipeline, history, new Set(trial), pick);
      trail.push(['prune', trial, !dropped]);
      if (dropped) {
        removed = trial;
        changed = true;
        break;
      }
    }
  }
  return { pick, removed, runs, trail };
}

export interface Path {
  source: number;
  target: number;
  via: number | null;
  kind: 'co-play' | Exclude<NodeKind, 'game'>;
  weight: number;
}

/** Up to `limit` paths between two games: a co-play edge or a shared tag/developer/publisher. */
export function relatedBy(graph: Graph, source: number, target: number, limit = 2): Path[] {
  const a = neighbours(graph, source);
  const b = neighbours(graph, target);
  const aw = new Map<number, number>();
  a.nodes.forEach((v, k) => aw.set(v, a.weights[k]));
  const bw = new Map<number, number>();
  b.nodes.forEach((v, k) => bw.set(v, b.weights[k]));
  const paths: Path[] = [];
  if (aw.has(target)) paths.push({ source, target, via: null, kind: 'co-play', weight: aw.get(target)! });
  const shared = [...aw.keys()].filter((v) => bw.has(v) && v >= graph.nGames).sort((x, y) => x - y);
  for (const v of shared) {
    paths.push({
      source,
      target,
      via: v,
      kind: graph.kinds[v] as Exclude<NodeKind, 'game'>,
      weight: Math.min(aw.get(v)!, bw.get(v)!),
    });
  }
  paths.sort((p, q) => (p.weight !== q.weight ? (q.weight > p.weight ? 1 : -1) : (p.via ?? -1) - (q.via ?? -1)));
  return paths.slice(0, limit);
}
