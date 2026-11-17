/**
 * Review evidence (`whyfinder export reviews`): what players say about a pick, preferring players
 * who also played your games, and the words both communities use.
 */

export interface Quote {
  text: string;
  hours: number;
  year: number | null;
  /** Other demo games (catalogue indices) this player reviewed. */
  also: number[];
}

export interface GameEvidence {
  terms: [string, number][];
  quotes: Quote[];
}

export interface Evidence {
  version: number;
  games: Record<string, GameEvidence>;
}

export type Voice = Quote & { yours: number[] };

export interface Voices {
  /** The game of yours these players also played; null when no quote bridges to your games. */
  bridge: number | null;
  /** Quotes from players who also played one of your games (the bridge game first). */
  quotes: Voice[];
  /** Other quotes, to make up `limit` in all. */
  others: Voice[];
}

/**
 * Up to `limit` quotes for a pick. `order` lists your games, strongest reason first. The bridge
 * game is the strongest reason that has at least one quote from a player who also played it.
 */
export function voices(ev: GameEvidence | undefined, order: number[], limit = 3): Voices {
  if (!ev || ev.quotes.length === 0) return { bridge: null, quotes: [], others: [] };
  const mine = new Set(order);
  const tagged = ev.quotes.map((q) => ({ ...q, yours: order.filter((j) => q.also.includes(j)) }));
  const bridge = order.find((j) => tagged.some((q) => q.yours.includes(j))) ?? null;
  if (bridge === null) return { bridge: null, quotes: [], others: tagged.slice(0, limit) };
  const ranked = tagged
    .map((q, k) => ({ q, k }))
    .filter(({ q }) => q.also.some((j) => mine.has(j)))
    .sort((a, b) => {
      const ab = Number(b.q.yours.includes(bridge)) - Number(a.q.yours.includes(bridge));
      return ab || b.q.yours.length - a.q.yours.length || a.k - b.k;
    })
    .map(({ q }) => q);
  const quotes = ranked.slice(0, limit);
  const others = tagged.filter((q) => q.yours.length === 0).slice(0, Math.max(0, limit - quotes.length));
  return { bridge, quotes, others };
}

/** Terms the pick's players use that players of your games use too, in the pick's order. */
export function sharedTerms(pick: GameEvidence | undefined, yours: (GameEvidence | undefined)[], limit = 8): string[] {
  if (!pick) return [];
  const theirs = new Set(yours.flatMap((g) => (g ? g.terms.map(([t]) => t) : [])));
  return pick.terms
    .map(([t]) => t)
    .filter((t) => theirs.has(t))
    .slice(0, limit);
}

export function topTerms(pick: GameEvidence | undefined, limit = 8): string[] {
  return pick ? pick.terms.slice(0, limit).map(([t]) => t) : [];
}
