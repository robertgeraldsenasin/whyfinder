import { describe, expect, it } from 'vitest';
import { type GameEvidence, sharedTerms, topTerms, voices } from './evidence';

const q = (text: string, also: number[]) => ({ text, hours: 10, year: 2016, also });

const pick: GameEvidence = {
  terms: [
    ['puzzles', 9],
    ['portals', 8],
    ['story', 7],
    ['coop', 5],
  ],
  quotes: [q('A', []), q('B', [7]), q('C', [3, 7]), q('D', [3]), q('E', [9])],
};

describe('voices', () => {
  it('prefers players who also played your strongest reason', () => {
    const v = voices(pick, [3, 7]);
    expect(v.bridge).toBe(3);
    expect(v.quotes.map((x) => x.text)).toEqual(['C', 'D', 'B']);
    expect(v.quotes[0].yours).toEqual([3, 7]);
    expect(v.others).toEqual([]);
  });

  it('falls back to the next reason with a bridge', () => {
    const v = voices(pick, [5, 7], 2);
    expect(v.bridge).toBe(7);
    expect(v.quotes.map((x) => x.text)).toEqual(['B', 'C']);
    const w = voices(pick, [9], 3);
    expect(w.quotes.map((x) => x.text)).toEqual(['E']);
    expect(w.others.map((x) => x.text)).toEqual(['A', 'B']);
  });

  it('shows plain quotes when nobody bridges', () => {
    const v = voices(pick, [42], 2);
    expect(v.bridge).toBeNull();
    expect(v.quotes).toEqual([]);
    expect(v.others.map((x) => x.text)).toEqual(['A', 'B']);
  });

  it('is empty without evidence', () => {
    expect(voices(undefined, [1])).toEqual({ bridge: null, quotes: [], others: [] });
    expect(voices({ terms: [], quotes: [] }, [1])).toEqual({ bridge: null, quotes: [], others: [] });
  });
});

describe('terms', () => {
  it('keeps the pick order and only words both communities use', () => {
    const yours = [{ terms: [['story', 3]], quotes: [] }, undefined, { terms: [['puzzles', 4]], quotes: [] }] as (
      | GameEvidence
      | undefined
    )[];
    expect(sharedTerms(pick, yours)).toEqual(['puzzles', 'story']);
    expect(sharedTerms(undefined, yours)).toEqual([]);
    expect(topTerms(pick, 2)).toEqual(['puzzles', 'portals']);
    expect(topTerms(undefined)).toEqual([]);
  });
});
