/**
 * The ten picks as a hand of cards (ADR-0018). Rank 0 is the Ace, then 2 to 10.
 *
 * The suit is data, not decoration: a pick's score is exactly the sum of its EASE^R (co-play) part
 * and its PageRank (graph) part over your games, so we can say which part carried it.
 * Hearts: the co-play part is at least the graph part (players in common).
 * Clubs: the graph part is larger (tags, studios and publishers).
 */

export type Suit = 'hearts' | 'clubs';

export interface Split {
  ease: number;
  ppr: number;
}

/** "A" for the best pick, then "2" to "10". */
export function rankLabel(rank: number): string {
  if (!Number.isInteger(rank) || rank < 0) throw new RangeError(`rank must be a non-negative integer, got ${rank}`);
  return rank === 0 ? 'A' : String(rank + 1);
}

/** The spoken form, for screen readers and labels. */
export function rankName(rank: number): string {
  return rank === 0 ? 'Ace' : rankLabel(rank);
}

/** Totals of each part over all your games (negative contributions included, as in the score). */
export function split(parts: readonly Split[]): Split {
  let ease = 0;
  let ppr = 0;
  for (const p of parts) {
    ease += p.ease;
    ppr += p.ppr;
  }
  return { ease, ppr };
}

/** Hearts when players in common carried the pick, clubs when the graph did. Ties go to hearts. */
export function suitOf(parts: readonly Split[]): Suit {
  const s = split(parts);
  return s.ease >= s.ppr ? 'hearts' : 'clubs';
}

export const SUITS: Record<Suit, { name: string; glyph: string; plain: string }> = {
  hearts: { name: 'Hearts', glyph: '♥', plain: 'mostly players in common' },
  clubs: { name: 'Clubs', glyph: '♣', plain: 'mostly tags and studios' },
};

/** SVG paths (24 × 24) for the suit pips and the four-pointed star used as a bullet. */
export const PIPS = {
  hearts: 'M12 21C12 21 3 14.5 3 8.6 3 5.5 5.4 3.5 8 3.5c1.8 0 3.2 1.1 4 2.5.8-1.4 2.2-2.5 4-2.5 2.6 0 5 2 5 5.1C21 14.5 12 21 12 21z',
  clubs: 'M12 2.6a4.3 4.3 0 0 1 3.9 6.1 4.3 4.3 0 1 1-2.6 7.5L15 21.4H9l1.7-5.2a4.3 4.3 0 1 1-2.6-7.5A4.3 4.3 0 0 1 12 2.6z',
  star: 'M12 1l2.3 8.7L23 12l-8.7 2.3L12 23l-2.3-8.7L1 12l8.7-2.3z',
} as const;
