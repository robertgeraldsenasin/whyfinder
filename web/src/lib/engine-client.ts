/** Promise-based client for the engine worker. */
import type { Explained } from '../engine/engine';
import type { Progress, ReadyInfo, Request, Response, Trace } from '../engine/protocol';
import type { ModelFile, Slice } from '../engine/types';

type Pending = { resolve: (r: Response) => void; reject: (e: Error) => void; onProgress?: (p: Progress) => void };
type Body<T> = T extends unknown ? Omit<T, 'id'> : never;

export class EngineClient {
  private worker: Worker;
  private next = 1;
  private pending = new Map<number, Pending>();

  constructor() {
    this.worker = new Worker(new URL('../engine/worker.ts', import.meta.url), { type: 'module' });
    this.worker.onmessage = (event: MessageEvent<Response>) => {
      const msg = event.data;
      const p = this.pending.get(msg.id);
      if (!p) return;
      if (msg.type === 'progress') {
        p.onProgress?.(msg.progress);
        return;
      }
      this.pending.delete(msg.id);
      if (msg.type === 'error') p.reject(new Error(msg.message));
      else p.resolve(msg);
    };
  }

  private call(body: Body<Request>, onProgress?: (p: Progress) => void): Promise<Response> {
    const id = this.next++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, onProgress });
      this.worker.postMessage({ ...body, id } as Request);
    });
  }

  async init(slice: Slice, model: ModelFile, onProgress?: (p: Progress) => void): Promise<ReadyInfo> {
    const r = await this.call({ type: 'init', slice, model }, onProgress);
    if (r.type !== 'ready') throw new Error('unexpected reply');
    return r.info;
  }

  async explain(history: [number, number][], beta?: number, theta?: number): Promise<Explained> {
    const r = await this.call({ type: 'explain', history, beta, theta });
    if (r.type !== 'explained') throw new Error('unexpected reply');
    return r.result;
  }

  async trace(seeds: number[]): Promise<Trace[]> {
    const r = await this.call({ type: 'trace', seeds });
    if (r.type !== 'traced') throw new Error('unexpected reply');
    return r.traces;
  }

  async neighbours(rows: number[]): Promise<{ game: number; top: [number, number, number][] }[]> {
    const r = await this.call({ type: 'neighbours', rows });
    if (r.type !== 'neighbours') throw new Error('unexpected reply');
    return r.rows;
  }

  async verify(onProgress?: (p: Progress) => void) {
    const r = await this.call({ type: 'verify' }, onProgress);
    if (r.type !== 'verified') throw new Error('unexpected reply');
    return r.result;
  }
}
