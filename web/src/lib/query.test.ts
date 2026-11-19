import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { Engine } from '../engine/engine';
import type { ModelFile, Slice, SliceGame } from '../engine/types';
import { allowedMask, clauses, describe as words, findGame, fold, merge, NO_FILTERS, parseQuery, passes } from './query';

const read = <T>(path: string): T => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8')) as T;
const slice = read<Slice>('../../public/data/demo-slice.json');
const games = slice.games;
const index = (title: string) => games.findIndex((g) => g.title === title);

const game = (over: Partial<SliceGame>): SliceGame => ({
  id: 1,
  title: 'Test',
  developer: null,
  publisher: null,
  tags: [],
  genres: [],
  year: 2015,
  price: 9.99,
  plays: 1,
  x: 0,
  y: 0,
  ...over,
});

describe('parsing', () => {
  it('reads anchors, tags, price and years, and reports the rest', () => {
    const q = parseQuery('like Portal 2, co-op, under $20, after 2012, blorp', games);
    expect(q.anchors).toEqual([index('Portal 2')]);
    expect(q.filters).toEqual({ tags: ['Co-op'], maxPrice: 20, yearMin: 2013, yearMax: null });
    expect(q.unresolved).toEqual(['blorp']);
  });

  it('understands the other year forms and free', () => {
    expect(parseQuery('since 2012', games).filters.yearMin).toBe(2012);
    expect(parseQuery('before 2010', games).filters.yearMax).toBe(2009);
    expect(parseQuery('until 2010', games).filters.yearMax).toBe(2010);
    expect(parseQuery('2014 to 2010', games).filters).toMatchObject({ yearMin: 2010, yearMax: 2014 });
    expect(parseQuery('2000s', games).filters).toMatchObject({ yearMin: 2000, yearMax: 2009 });
    expect(parseQuery('free', games).filters.maxPrice).toBe(0);
    expect(parseQuery('horror and open world', games).filters.tags).toEqual(['Horror', 'Open World']);
  });

  it('keeps titles with separators whole and accepts bare titles', () => {
    const papers = index('Papers, Please');
    expect(papers).toBeGreaterThanOrEqual(0);
    expect(clauses('like Papers, Please, horror', games)).toEqual(['like Papers, Please', 'horror']);
    expect(parseQuery('like Papers, Please, horror', games).anchors).toEqual([papers]);
    expect(parseQuery('Undertale', games).anchors).toEqual([index('Undertale')]);
  });

  it('finds games by exact title first, then by prefix, then by the most played', () => {
    expect(findGame('portal 2', games)).toBe(index('Portal 2'));
    expect(findGame('x', games)).toBeNull();
    expect(fold('Co-op')).toBe(fold('co op'));
  });
});

describe('filters', () => {
  it('pass only games that meet every filter; unknown price or year fails', () => {
    const f = { tags: ['Co-op'], maxPrice: 10, yearMin: 2010, yearMax: 2016 };
    expect(passes(game({ tags: ['Co-op', 'Indie'] }), f)).toBe(true);
    expect(passes(game({ tags: ['Indie'] }), f)).toBe(false);
    expect(passes(game({ tags: ['Co-op'], price: 19.99 }), f)).toBe(false);
    expect(passes(game({ tags: ['Co-op'], price: null }), f)).toBe(false);
    expect(passes(game({ tags: ['Co-op'], year: 2009 }), f)).toBe(false);
    expect(passes(game({ tags: ['Co-op'], year: null }), f)).toBe(false);
    expect(allowedMask(games, NO_FILTERS)).toBeNull();
  });

  it('read as chips and merge', () => {
    expect(words({ tags: ['Horror'], maxPrice: 0, yearMin: 2010, yearMax: 2010 })).toEqual(['Horror', 'Free', '2010']);
    expect(words({ tags: [], maxPrice: 19.5, yearMin: 2012, yearMax: null })).toEqual(['Under $19.50', '2012 or later']);
    expect(merge({ ...NO_FILTERS, tags: ['A'], maxPrice: 5 }, { ...NO_FILTERS, tags: ['B', 'A'] })).toEqual({
      tags: ['A', 'B'],
      maxPrice: 5,
      yearMin: null,
      yearMax: null,
    });
  });

  it('never let a filtered pick break a filter (FR-23)', () => {
    const engine = new Engine(slice, read<ModelFile>('../../public/data/model.json'));
    const history: [number, number][] = [
      [index('Portal 2'), engine.weight(40)],
      [index('Borderlands 2'), engine.weight(60)],
    ];
    const f = parseQuery('co-op, under $15, since 2010', games).filters;
    const mask = allowedMask(games, f)!;
    const rec = engine.run(history, { allowed: mask });
    expect(rec.picks.length).toBeGreaterThan(0);
    for (const p of rec.picks) expect(passes(games[p], f)).toBe(true);
    const none = engine.run(history, { allowed: games.map(() => false) });
    expect(none.picks).toEqual([]);
  });
});
