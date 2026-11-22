/**
 * Live mode (ADR-0008, ADR-0019): open the demo with `?api=<url>` and the Words step also asks a
 * running copy of the API for its sentences about the same pick. That copy can have a local model
 * writing them; the static demo cannot. Nothing else in the demo depends on it.
 *
 *   docker run -p 8000:8000 ghcr.io/robertgeraldsenasin/whyfinder-api
 *   …/whyfinder/?api=http://localhost:8000
 */
import type { Ref } from './words';

export interface ApiExplain {
  game_id: string;
  title: string;
  /** 1-based rank among the API's picks; null when the game is not among them. */
  rank: number | null;
  claims: { text: string; evidence: Ref[] }[];
  checker: { passed: boolean; fallback_used: boolean; reasons: string[] };
  model_version: string;
}

export class ApiError extends Error {}

/** The API base from a query string, if `api` holds an http(s) URL; trailing slashes dropped. */
export function apiBase(search: string): string | null {
  const raw = new URLSearchParams(search).get('api');
  if (!raw) return null;
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return null;
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
  return url.href.replace(/\/+$/, '');
}

/** POST /explain for one pick. Errors come back as ApiError with something a person can act on. */
export async function explainRemote(
  base: string,
  liked: string[],
  gameId: string,
  opts: { fetch?: typeof fetch; timeoutMs?: number } = {},
): Promise<ApiExplain> {
  const wait = opts.timeoutMs ?? 90_000;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), wait);
  try {
    const res = await (opts.fetch ?? fetch)(`${base}/explain`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ liked_game_ids: liked, game_id: gameId }),
      signal: ctrl.signal,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const problem = (await res.json()) as { detail?: string; title?: string };
        detail = problem.detail ?? problem.title ?? detail;
      } catch {
        // Not problem+json: keep the status text.
      }
      throw new ApiError(`the API answered ${res.status}: ${detail}`);
    }
    return (await res.json()) as ApiExplain;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (ctrl.signal.aborted) throw new ApiError(`no answer from ${base} within ${Math.round(wait / 1000)} s`);
    throw new ApiError(`could not reach ${base}; is it running, and does it allow this page's origin?`);
  } finally {
    clearTimeout(timer);
  }
}
