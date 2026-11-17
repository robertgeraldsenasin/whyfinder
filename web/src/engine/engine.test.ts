/**
 * Golden cross-check (ADR-0015): the TypeScript engine must reproduce the Python core on the demo
 * slice. Goldens come from `uv run whyfinder export model`; tests/golden/test_web_goldens.py keeps
 * them in step with the Python code.
 */
import { readFileSync } from 'node:fs';
import { beforeAll, describe, expect, it } from 'vitest';
import { scaleConstant } from './blend';
import { Engine } from './engine';
import { push } from './ppr';
import type { HistoryEntry, ModelFile, Slice } from './types';

const read = <T>(path: string): T => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8')) as T;
const slice = read<Slice>('../../public/data/demo-slice.json');
const model = read<ModelFile>('../../public/data/model.json');

interface GoldenPick {
  pick: number;
  score: number;
  attributions: [number, number, number, number][];
  counterfactual: { removed: number[]; runs: number };
  paths: [number | null, string, number][];
}
interface GoldenCase {
  titles: string[];
  history: HistoryEntry[];
  candidates: number[];
  candidateScores: number[];
  relevanceTop: number[];
  picks: GoldenPick[];
  variety: boolean[];
  dppGains: number[];
}
interface Goldens {
  cB: number;
  cPi: number;
  graph: { nodes: number; edges: number; degree: number[]; names: string[] };
  bRows: Record<string, number[]>;
  piRows: Record<string, [number, number][]>;
  push: { seed: number; rounds: number; pushes: number; residual: number; p: [number, number][] }[];
  cases: GoldenCase[];
}
const goldens = read<Goldens>('./__goldens__/goldens.json');

/** |a − b| ≤ 1e-9 · max(1, |b|) */
function close(actual: number, expected: number, tol = 1e-9): void {
  const bound = tol * Math.max(1, Math.abs(expected));
  if (!(Math.abs(actual - expected) <= bound)) {
    expect.fail(`expected ${expected}, got ${actual} (|Δ| = ${Math.abs(actual - expected)} > ${bound})`);
  }
}

let engine: Engine;
beforeAll(() => {
  engine = new Engine(slice, model);
});

describe('EASE^R', () => {
  it('reproduces B rows from the Python core', () => {
    for (const [index, row] of Object.entries(goldens.bRows)) {
      const mine = engine.bRow(Number(index));
      row.forEach((v, i) => close(mine[i], v, 1e-9));
      expect(mine[Number(index)]).toBe(0);
    }
  });
  it('reproduces c_B from the full matrix', () => {
    close(scaleConstant(engine.B, engine.n), goldens.cB, 1e-9);
  });
});

describe('game graph', () => {
  it('has the same nodes, edges and weighted degrees', () => {
    expect(engine.graph.kinds.length).toBe(goldens.graph.nodes);
    expect(engine.graph.indices.length / 2).toBe(goldens.graph.edges);
    expect(engine.graph.names.slice(engine.graph.nGames)).toEqual(goldens.graph.names);
    goldens.graph.degree.forEach((d, v) => close(engine.graph.degree[v], d, 1e-12));
  });
});

describe('PPR forward push', () => {
  it('matches rounds, pushes and the estimate', () => {
    for (const g of goldens.push) {
      const r = push(engine.graph, g.seed, model.params.restartAlpha, model.params.pushEps);
      expect(r.rounds).toBe(g.rounds);
      expect(r.pushes).toBe(g.pushes);
      close(r.residualMass, g.residual);
      const expected = new Map(g.p);
      r.p.forEach((v, i) => close(v, expected.get(i) ?? 0));
    }
  });
  it('matches Π rows', () => {
    for (const [index, entries] of Object.entries(goldens.piRows)) {
      const row = engine.piRow(Number(index));
      const expected = new Map(entries);
      expect([...row.keys()].filter((i) => row[i] !== 0)).toEqual(entries.map(([i]) => i));
      row.forEach((v, i) => close(v, expected.get(i) ?? 0));
    }
  });
});

describe('pipeline and explanations', () => {
  it('covers at least four histories', () => {
    expect(goldens.cases.length).toBeGreaterThanOrEqual(4);
  });
  for (const [k, c] of goldens.cases.entries()) {
    it(`case ${k + 1}: ${c.titles.join(' + ')}`, () => {
      const out = engine.explain(c.history);
      expect(out.candidates).toEqual(c.candidates);
      out.topScores.forEach(([, s], t) => close(s, c.candidateScores[t]));
      expect(out.relevanceTop).toEqual(c.relevanceTop);
      expect(out.picks).toEqual(c.picks.map((p) => p.pick));
      expect(out.variety).toEqual(c.variety);
      out.steps.forEach((s, t) => close(s.gain, c.dppGains[t]));
      out.explanations.forEach((e, t) => {
        const g = c.picks[t];
        close(e.score, g.score);
        expect(e.attributions.map((a) => a.game)).toEqual(g.attributions.map(([j]) => j));
        e.attributions.forEach((a, u) => {
          close(a.total, g.attributions[u][1]);
          close(a.ease, g.attributions[u][2]);
          close(a.ppr, g.attributions[u][3]);
        });
        const sum = e.attributions.reduce((acc, a) => acc + a.total, 0);
        close(sum, e.score); // exact additivity holds in the browser too
        expect(e.counterfactual.removed).toEqual(g.counterfactual.removed);
        expect(e.counterfactual.runs).toBe(g.counterfactual.runs);
        expect(e.paths.map((p) => [p.via, p.kind])).toEqual(g.paths.map(([via, kind]) => [via, kind]));
      });
    });
  }
});

describe('constants', () => {
  it('recomputes c_Π from every Π row', () => {
    const live = engine.verifyConstants();
    close(live.cB, goldens.cB);
    close(live.cPi, goldens.cPi);
  });
});
