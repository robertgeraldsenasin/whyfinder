import { describe, expect, it } from 'vitest';
import { ApiError, apiBase, explainRemote } from './api';

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('apiBase', () => {
  it('reads an http(s) URL from ?api= and drops trailing slashes', () => {
    expect(apiBase('?api=http://localhost:8000/')).toBe('http://localhost:8000');
    expect(apiBase('?api=https%3A%2F%2Fapi.example%2Fwhyfinder%2F&x=1')).toBe('https://api.example/whyfinder');
  });

  it('ignores a missing, malformed or non-http value', () => {
    expect(apiBase('')).toBeNull();
    expect(apiBase('?api=')).toBeNull();
    expect(apiBase('?api=not a url')).toBeNull();
    expect(apiBase('?api=javascript:alert(1)')).toBeNull();
    expect(apiBase('?api=file:///etc/passwd')).toBeNull();
  });
});

describe('explainRemote', () => {
  const answer = {
    game_id: '440',
    title: 'Team Fortress 2',
    rank: 2,
    claims: [{ text: 'Portal 2 is the biggest driver of this pick (41%).', evidence: [{ type: 'attribution', game_id: '620', share: 0.41 }] }],
    checker: { passed: true, fallback_used: true, reasons: [] },
    model_version: 'blend-slice-1',
  };

  it('posts the liked games and the pick, and returns the answer', async () => {
    let sent: { url: string; body: unknown; type: string | null } | null = null;
    const fake = (async (url: string, init: RequestInit) => {
      sent = { url, body: JSON.parse(String(init.body)), type: new Headers(init.headers).get('content-type') };
      return json(200, answer);
    }) as unknown as typeof fetch;
    await expect(explainRemote('http://api.test', ['620', '220'], '440', { fetch: fake })).resolves.toEqual(answer);
    expect(sent).toEqual({ url: 'http://api.test/explain', body: { liked_game_ids: ['620', '220'], game_id: '440' }, type: 'application/json' });
  });

  it('turns a problem into a readable error', async () => {
    const fake = (async () => json(404, { title: 'Not found', detail: 'game 440 is not in the catalogue' })) as unknown as typeof fetch;
    await expect(explainRemote('http://api.test', ['620'], '440', { fetch: fake })).rejects.toThrow('the API answered 404: game 440 is not in the catalogue');
    const plain = (async () => new Response('oops', { status: 502, statusText: 'Bad Gateway' })) as unknown as typeof fetch;
    await expect(explainRemote('http://api.test', ['620'], '440', { fetch: plain })).rejects.toThrow('the API answered 502: Bad Gateway');
  });

  it('says so when the API cannot be reached or does not answer in time', async () => {
    const down = (async () => {
      throw new TypeError('Failed to fetch');
    }) as unknown as typeof fetch;
    await expect(explainRemote('http://api.test', ['620'], '440', { fetch: down })).rejects.toBeInstanceOf(ApiError);
    await expect(explainRemote('http://api.test', ['620'], '440', { fetch: down })).rejects.toThrow(/could not reach http:\/\/api\.test/);
    const slow = ((_: string, init: RequestInit) =>
      new Promise((_, reject) => init.signal!.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))))) as unknown as typeof fetch;
    await expect(explainRemote('http://api.test', ['620'], '440', { fetch: slow, timeoutMs: 1000 })).rejects.toThrow('no answer from http://api.test within 1 s');
  });
});
