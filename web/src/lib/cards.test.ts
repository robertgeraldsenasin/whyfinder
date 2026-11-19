import { describe, expect, it } from 'vitest';
import { rankLabel, rankName, split, suitOf, SUITS } from './cards';

describe('ranks', () => {
  it('deal the best pick as the Ace, then 2 to 10', () => {
    expect(Array.from({ length: 10 }, (_, r) => rankLabel(r))).toEqual(['A', '2', '3', '4', '5', '6', '7', '8', '9', '10']);
    expect(rankName(0)).toBe('Ace');
    expect(rankName(4)).toBe('5');
  });

  it('reject ranks that are not cards', () => {
    expect(() => rankLabel(-1)).toThrow(RangeError);
    expect(() => rankLabel(1.5)).toThrow(RangeError);
    expect(() => rankLabel(Number.NaN)).toThrow(RangeError);
  });
});

describe('suits', () => {
  it('follow the larger part of the exact score', () => {
    expect(suitOf([{ ease: 0.6, ppr: 0.1 }, { ease: 0.1, ppr: 0.2 }])).toBe('hearts');
    expect(suitOf([{ ease: 0.1, ppr: 0.5 }, { ease: 0.2, ppr: 0.1 }])).toBe('clubs');
  });

  it('count negative contributions the way the score does', () => {
    // EASE^R pulls away from this pick through one of your games: the graph carried it.
    expect(split([{ ease: 0.4, ppr: 0.1 }, { ease: -0.35, ppr: 0.1 }])).toEqual({ ease: 0.4 - 0.35, ppr: 0.2 });
    expect(suitOf([{ ease: 0.4, ppr: 0.1 }, { ease: -0.35, ppr: 0.1 }])).toBe('clubs');
  });

  it('give ties and an empty hand to hearts', () => {
    expect(suitOf([{ ease: 0.25, ppr: 0.25 }])).toBe('hearts');
    expect(suitOf([])).toBe('hearts');
  });

  it('name each suit in plain words', () => {
    expect(SUITS.hearts.plain).toMatch(/players/);
    expect(SUITS.clubs.plain).toMatch(/tags/);
  });
});
