/**
 * The heterogeneous game graph: games, then tags, developers and publishers (each sorted by name).
 * Twin of src/whyfinder/graph/build.py. Neighbours are kept in ascending node order and weighted
 * degrees are summed in that order, so both engines produce identical numbers.
 */
import type { Params, SliceGame } from './types';

export type NodeKind = 'game' | 'tag' | 'developer' | 'publisher';

export interface Graph {
  nGames: number;
  kinds: NodeKind[];
  names: string[];
  indptr: Int32Array;
  indices: Int32Array;
  weights: Float64Array;
  degree: Float64Array;
}

/** Python's default string order (by code point), so sorted names match the Python engine. */
export function byCodePoint(a: string, b: string): number {
  const x = Array.from(a);
  const y = Array.from(b);
  const n = Math.min(x.length, y.length);
  for (let i = 0; i < n; i++) {
    const d = x[i].codePointAt(0)! - y[i].codePointAt(0)!;
    if (d !== 0) return d;
  }
  return x.length - y.length;
}

function unique<T>(items: T[]): T[] {
  return [...new Set(items)];
}

/** idf(t) = ln(1 + n / df(t)) over each game's top tags; keys in code-point order. */
export function tagIdf(games: SliceGame[], tagsPerGame: number): Map<string, number> {
  const df = new Map<string, number>();
  for (const g of games) for (const t of unique(g.tags.slice(0, tagsPerGame))) df.set(t, (df.get(t) ?? 0) + 1);
  const n = games.length;
  const out = new Map<string, number>();
  for (const t of [...df.keys()].sort(byCodePoint)) out.set(t, Math.log(1 + n / df.get(t)!));
  return out;
}

/** Co-play cosine S_ij = G_ij / (d_i·d_j), d = √max(G_ii, 1), zero diagonal. */
export function cosine(G: Float64Array, n: number): Float64Array {
  const d = new Float64Array(n);
  for (let i = 0; i < n; i++) d[i] = Math.sqrt(Math.max(G[i * n + i], 1));
  const S = new Float64Array(n * n);
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) S[i * n + j] = i === j ? 0 : G[i * n + j] / (d[i] * d[j]);
  }
  return S;
}

/** Each game's `perGame` most co-played games (cosine > 0), ties by index. */
export function coplayNeighbours(S: Float64Array, n: number, perGame: number): number[][] {
  const out: number[][] = [];
  const order = new Array<number>(n);
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) order[j] = j;
    const row = (j: number) => (j === i ? 0 : S[i * n + j]);
    order.sort((a, b) => (row(a) !== row(b) ? (row(b) > row(a) ? 1 : -1) : a - b));
    out.push(order.slice(0, perGame).filter((j) => row(j) > 0));
  }
  return out;
}

export function buildGraph(games: SliceGame[], S: Float64Array, params: Params): Graph {
  const n = games.length;
  const { tagsPerGame, coplayPerGame, weights } = params;
  const idf = tagIdf(games, tagsPerGame);
  const developers = unique(games.map((g) => g.developer).filter((d): d is string => !!d)).sort(byCodePoint);
  const publishers = unique(games.map((g) => g.publisher).filter((p): p is string => !!p)).sort(byCodePoint);
  const tags = [...idf.keys()];
  const kinds: NodeKind[] = [
    ...Array<NodeKind>(n).fill('game'),
    ...Array<NodeKind>(tags.length).fill('tag'),
    ...Array<NodeKind>(developers.length).fill('developer'),
    ...Array<NodeKind>(publishers.length).fill('publisher'),
  ];
  const names = [...games.map((_, i) => `game:${i}`), ...tags, ...developers, ...publishers];
  const tagNode = new Map(tags.map((t, k) => [t, n + k]));
  const devNode = new Map(developers.map((d, k) => [d, n + tags.length + k]));
  const pubNode = new Map(publishers.map((p, k) => [p, n + tags.length + developers.length + k]));

  // Insertion-ordered like Python's dict; the stored weight is the max over duplicates.
  const edges = new Map<string, [number, number, number]>();
  const add = (a: number, b: number, w: number) => {
    if (a === b || w <= 0) return;
    const lo = Math.min(a, b);
    const hi = Math.max(a, b);
    const key = `${lo},${hi}`;
    const prev = edges.get(key);
    edges.set(key, [lo, hi, Math.max(prev ? prev[2] : 0, w)]);
  };
  games.forEach((g, i) => {
    for (const t of unique(g.tags.slice(0, tagsPerGame))) add(i, tagNode.get(t)!, weights.tag * idf.get(t)!);
    if (g.developer) add(i, devNode.get(g.developer)!, weights.developer);
    if (g.publisher) add(i, pubNode.get(g.publisher)!, weights.publisher);
  });
  coplayNeighbours(S, n, coplayPerGame).forEach((nbs, i) => {
    for (const j of nbs) add(i, j, weights.coplay * S[i * n + j]);
  });

  const adjacency: [number, number][][] = kinds.map(() => []);
  for (const [a, b, w] of edges.values()) {
    adjacency[a].push([b, w]);
    adjacency[b].push([a, w]);
  }
  const indptr = new Int32Array(kinds.length + 1);
  const indices: number[] = [];
  const values: number[] = [];
  const degree = new Float64Array(kinds.length);
  adjacency.forEach((row, v) => {
    row.sort((x, y) => x[0] - y[0]);
    let total = 0;
    for (const [u, w] of row) {
      indices.push(u);
      values.push(w);
      total += w;
    }
    degree[v] = total;
    indptr[v + 1] = indices.length;
  });
  return {
    nGames: n,
    kinds,
    names,
    indptr,
    indices: Int32Array.from(indices),
    weights: Float64Array.from(values),
    degree,
  };
}

export function neighbours(graph: Graph, v: number): { nodes: Int32Array; weights: Float64Array } {
  const start = graph.indptr[v];
  const end = graph.indptr[v + 1];
  return { nodes: graph.indices.subarray(start, end), weights: graph.weights.subarray(start, end) };
}
