/** Messages between the page and the engine worker. */
import type { BuildTimings, Explained } from './engine';
import type { NodeKind } from './graph';
import type { ModelFile, Slice } from './types';

export type Request =
  | { id: number; type: 'init'; slice: Slice; model: ModelFile }
  | { id: number; type: 'explain'; history: [number, number][]; beta?: number; theta?: number }
  | { id: number; type: 'trace'; seeds: number[] }
  | { id: number; type: 'neighbours'; rows: number[] }
  | { id: number; type: 'verify' };

export interface Hub {
  node: number;
  kind: NodeKind;
  name: string;
  x: number;
  y: number;
  games: number;
}

export interface ReadyInfo {
  timings: BuildTimings;
  nodes: number;
  edges: number;
  gramOrder: number[];
  gramImage: Uint8ClampedArray;
  hubs: Hub[];
}

export interface Trace {
  seed: number;
  rounds: number;
  pushes: number;
  residualMass: number;
  trace: { active: number; p: Float32Array; settled: number; residual: number }[];
  top: [number, number][];
  degree: number;
}

export interface Progress {
  phase: string;
  done: number;
  total: number;
}

export type Response =
  | { id: number; type: 'progress'; progress: Progress }
  | { id: number; type: 'ready'; info: ReadyInfo }
  | { id: number; type: 'explained'; result: Explained }
  | { id: number; type: 'traced'; traces: Trace[] }
  | { id: number; type: 'neighbours'; rows: { game: number; top: [number, number, number][] }[] }
  | {
      id: number;
      type: 'verified';
      result: { cB: number; cPi: number; seconds: number; cBModel: number; cPiModel: number };
    }
  | { id: number; type: 'error'; message: string };

/** Order points along a Hilbert curve so neighbours on the map sit together in the heat map. */
export function hilbertOrder(points: [number, number][], bits = 6): number[] {
  const side = 1 << bits;
  const index = (px: number, py: number): number => {
    let x = Math.min(side - 1, Math.max(0, Math.floor(px * side)));
    let y = Math.min(side - 1, Math.max(0, Math.floor(py * side)));
    let d = 0;
    for (let s = side >> 1; s > 0; s >>= 1) {
      const rx = (x & s) > 0 ? 1 : 0;
      const ry = (y & s) > 0 ? 1 : 0;
      d += s * s * ((3 * rx) ^ ry);
      if (ry === 0) {
        if (rx === 1) {
          x = side - 1 - x;
          y = side - 1 - y;
        }
        [x, y] = [y, x];
      }
    }
    return d;
  };
  return points
    .map(([x, y], i) => [index(x, y), i] as const)
    .sort((a, b) => a[0] - b[0] || a[1] - b[1])
    .map(([, i]) => i);
}
