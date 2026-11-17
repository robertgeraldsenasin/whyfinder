/**
 * The glass-box engine as one object: everything the worker, the UI and the golden tests use.
 * Builds G, EASE^R and the graph once; Π rows and M rows are computed on demand and cached.
 */
import { blendRow, confidence, scaleConstant, topKRow } from './blend';
import { ease, type EaseProgress, unpackUpper } from './ease';
import { attributions, type Contribution, type Counterfactual, greedyCounterfactual, type Path, relatedBy } from './explain';
import { buildGraph, cosine, type Graph } from './graph';
import { type DppStep, type SparseVector, tfidfVectors } from './dpp';
import { recommend, type Recommendation } from './pipeline';
import { piRow, push, type PushResult } from './ppr';
import type { HistoryEntry, ModelFile, Params, Slice, SliceGame } from './types';

export interface PickExplanation {
  pick: number;
  rank: number;
  score: number;
  variety: boolean;
  attributions: Contribution[];
  counterfactual: Counterfactual;
  paths: Path[];
}

export interface Explained extends Omit<Recommendation, 'scores' | 'steps'> {
  history: HistoryEntry[];
  topScores: [number, number][];
  /** EASE^R and PageRank parts of the score for the 20 best candidates: [index, ease, ppr]. */
  parts: [number, number, number][];
  steps: DppStep[];
  explanations: PickExplanation[];
  timings: { score: number; dpp: number; explain: number; pi: number };
}

export interface BuildTimings {
  gram: number;
  ease: number;
  graph: number;
}

export function dppFeatures(games: SliceGame[]): string[][] {
  return games.map((g) => [...g.tags, ...g.genres.map((x) => `genre:${x}`)]);
}

const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());

export class Engine {
  readonly n: number;
  readonly games: SliceGame[];
  readonly gameIds: number[];
  readonly params: Params;
  readonly cB: number;
  readonly cPi: number;
  readonly G: Float64Array;
  readonly B: Float64Array;
  readonly S: Float64Array;
  readonly graph: Graph;
  readonly vectors: SparseVector[];
  readonly timings: BuildTimings;
  private piCache = new Map<number, Float64Array>();
  private mCache = new Map<string, Float64Array>();

  constructor(slice: Slice, model: ModelFile, onProgress?: (p: EaseProgress) => void) {
    this.games = slice.games;
    this.n = slice.gram.n;
    this.gameIds = slice.games.map((g) => g.id);
    this.params = model.params;
    this.cB = model.cB;
    this.cPi = model.cPi;
    const t0 = now();
    this.G = unpackUpper(slice.gram.packed_upper, this.n);
    const t1 = now();
    this.B = ease(this.G, this.n, this.params.lambda, onProgress);
    const t2 = now();
    this.S = cosine(this.G, this.n);
    this.graph = buildGraph(this.games, this.S, this.params);
    this.vectors = tfidfVectors(dppFeatures(this.games));
    const t3 = now();
    this.timings = { gram: t1 - t0, ease: t2 - t1, graph: t3 - t2 };
  }

  bRow(j: number): Float64Array {
    return this.B.subarray(j * this.n, (j + 1) * this.n);
  }

  piRow(j: number): Float64Array {
    let row = this.piCache.get(j);
    if (!row) {
      const { restartAlpha, pushEps, topM } = this.params;
      row = piRow(this.graph, j, restartAlpha, pushEps, topM);
      this.piCache.set(j, row);
    }
    return row;
  }

  pushTrace(seed: number): PushResult {
    return push(this.graph, seed, this.params.restartAlpha, this.params.pushEps, { trace: true });
  }

  mRow(j: number, beta = this.params.beta): Float64Array {
    const key = `${j}:${beta}`;
    let row = this.mCache.get(key);
    if (!row) {
      row = topKRow(blendRow(this.bRow(j), this.piRow(j), j, beta, this.cB, this.cPi), this.params.topKPerRow);
      this.mCache.set(key, row);
    }
    return row;
  }

  weight(hours: number): number {
    return confidence(hours, this.params.confidence.alpha, this.params.confidence.eps);
  }

  run(history: HistoryEntry[], opts: { beta?: number; theta?: number; allowed?: boolean[] | null } = {}): Recommendation {
    const beta = opts.beta ?? this.params.beta;
    return recommend(history, (j) => this.mRow(j, beta), this.n, {
      vectors: this.vectors,
      gameIds: this.gameIds,
      k: this.params.k,
      nCandidates: this.params.candidates,
      theta: opts.theta ?? this.params.theta,
      allowed: opts.allowed ?? null,
    });
  }

  /** The full answer: picks, exact attributions, a counterfactual and paths for every pick. */
  explain(history: HistoryEntry[], opts: { beta?: number; theta?: number; allowed?: boolean[] | null } = {}): Explained {
    const beta = opts.beta ?? this.params.beta;
    const t0 = now();
    for (const [j] of history) this.piRow(j);
    const t1 = now();
    const rec = this.run(history, opts);
    const t2 = now();
    const pipeline = (h: HistoryEntry[]) => this.run(h, opts).picks;
    const explanations = rec.picks.map((pick, rank) => {
      const parts = attributions(
        history,
        pick,
        (j) => this.mRow(j, beta),
        (j) => this.bRow(j),
        (j) => this.piRow(j),
        beta,
        this.cB,
        this.cPi,
        this.gameIds,
      );
      return {
        pick,
        rank,
        score: rec.scores[pick],
        variety: rec.variety[rank],
        attributions: parts,
        counterfactual: greedyCounterfactual(pipeline, history, pick, parts.map((c) => c.game)),
        paths: relatedBy(this.graph, parts[0].game, pick),
      };
    });
    const t3 = now();
    const scoreParts = rec.candidates.slice(0, 20).map((i) => {
      let ease = 0;
      let ppr = 0;
      for (const [j, x] of history) {
        ease += x * (beta * (this.bRow(j)[i] / this.cB));
        ppr += x * ((1 - beta) * (this.piRow(j)[i] / this.cPi));
      }
      return [i, ease, ppr] as [number, number, number];
    });
    return {
      history,
      parts: scoreParts,
      candidates: rec.candidates,
      relevanceTop: rec.relevanceTop,
      picks: rec.picks,
      variety: rec.variety,
      steps: rec.steps,
      topScores: rec.candidates.map((i) => [i, rec.scores[i]]),
      explanations,
      timings: { pi: t1 - t0, score: t2 - t1, dpp: 0, explain: t3 - t2 },
    };
  }

  /** Recompute c_B and, from every Π row, c_Π: the live check against the offline build. */
  verifyConstants(onProgress?: (done: number, total: number) => void): { cB: number; cPi: number; seconds: number } {
    const t0 = now();
    const Pi = new Float64Array(this.n * this.n);
    for (let j = 0; j < this.n; j++) {
      Pi.set(this.piRow(j), j * this.n);
      if (onProgress && (j % 20 === 0 || j === this.n - 1)) onProgress(j + 1, this.n);
    }
    return { cB: scaleConstant(this.B, this.n), cPi: scaleConstant(Pi, this.n), seconds: (now() - t0) / 1000 };
  }
}
