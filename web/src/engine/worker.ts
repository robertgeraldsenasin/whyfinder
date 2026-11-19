/// <reference lib="webworker" />
/**
 * The engine runs here so the page stays fluid: EASE^R's inverse, pushes and counterfactual
 * re-runs never block an animation frame.
 */
import { Engine } from './engine';
import { neighbours } from './graph';
import type { Request, Response } from './protocol';
import { hilbertOrder } from './protocol';

let engine: Engine | null = null;
const post = (message: Response, transfer: Transferable[] = []) =>
  (self as unknown as DedicatedWorkerGlobalScope).postMessage(message, transfer);

function gramImage(e: Engine, order: number[]): Uint8ClampedArray {
  const n = e.n;
  let max = 0;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) if (i !== j) max = Math.max(max, e.G[i * n + j]);
  const img = new Uint8ClampedArray(n * n);
  const scale = 255 / Math.log1p(max);
  for (let a = 0; a < n; a++) {
    for (let b = 0; b < n; b++) {
      const i = order[a];
      const j = order[b];
      img[a * n + b] = i === j ? 0 : Math.round(Math.log1p(e.G[i * n + j]) * scale);
    }
  }
  return img;
}

self.onmessage = (event: MessageEvent<Request>) => {
  const req = event.data;
  try {
    if (req.type === 'init') {
      engine = new Engine(req.slice, req.model, (p) => post({ id: req.id, type: 'progress', progress: p }));
      const e = engine;
      const order = hilbertOrder(e.games.map((g) => [g.x, g.y]));
      const image = gramImage(e, order);
      const hubs = [];
      for (let v = e.graph.nGames; v < e.graph.kinds.length; v++) {
        const { nodes } = neighbours(e.graph, v);
        let x = 0;
        let y = 0;
        let count = 0;
        for (const u of nodes) {
          if (u < e.n) {
            x += e.games[u].x;
            y += e.games[u].y;
            count++;
          }
        }
        hubs.push({ node: v, kind: e.graph.kinds[v], name: e.graph.names[v], x: x / count, y: y / count, games: count });
      }
      post(
        {
          id: req.id,
          type: 'ready',
          info: {
            timings: e.timings,
            nodes: e.graph.kinds.length,
            edges: e.graph.indices.length / 2,
            gramOrder: order,
            gramImage: image,
            hubs,
          },
        },
        [image.buffer],
      );
      return;
    }
    if (!engine) throw new Error('engine not initialised');
    const e = engine;
    if (req.type === 'explain') {
      const history = req.history.map(([j, hours]) => [j, e.weight(hours)] as [number, number]);
      post({
        id: req.id,
        type: 'explained',
        result: e.explain(history, { beta: req.beta, theta: req.theta, allowed: req.allowed ?? null }),
      });
    } else if (req.type === 'trace') {
      const traces = req.seeds.map((seed) => {
        const r = e.pushTrace(seed);
        const top: [number, number][] = [];
        e.piRow(seed).forEach((v, i) => {
          if (v > 0) top.push([i, v]);
        });
        top.sort((a, b) => b[1] - a[1]);
        return {
          seed,
          rounds: r.rounds,
          pushes: r.pushes,
          residualMass: r.residualMass,
          trace: (r.trace ?? []).map((t) => ({ active: t.active.length, p: t.p, settled: t.settled, residual: t.residual })),
          top: top.slice(0, 12),
          degree: e.graph.degree[seed],
        };
      });
      post({ id: req.id, type: 'traced', traces });
    } else if (req.type === 'neighbours') {
      const rows = req.rows.map((j) => {
        const b = e.bRow(j);
        const order = Array.from(b.keys()).filter((i) => i !== j);
        order.sort((x, y) => b[y] - b[x]);
        return { game: j, top: order.slice(0, 8).map((i) => [i, b[i], e.G[j * e.n + i]] as [number, number, number]) };
      });
      post({ id: req.id, type: 'neighbours', rows });
    } else if (req.type === 'verify') {
      const result = e.verifyConstants((done, total) =>
        post({ id: req.id, type: 'progress', progress: { phase: 'pi', done, total } }),
      );
      post({ id: req.id, type: 'verified', result: { ...result, cBModel: e.cB, cPiModel: e.cPi } });
    }
  } catch (error) {
    post({ id: req.id, type: 'error', message: error instanceof Error ? error.message : String(error) });
  }
};
