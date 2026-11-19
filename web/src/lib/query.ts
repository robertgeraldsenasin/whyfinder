/**
 * Natural-language queries and filters (FR-18, FR-23), deterministic and small on purpose: the demo
 * explains what it understood and what it did not, instead of guessing.
 *
 * A query is a list of clauses separated by commas, semicolons or " and ":
 *
 * | Clause | Becomes |
 * | --- | --- |
 * | `like Hades`, `similar to Portal 2`, a bare game title | an anchor: that game joins your sky |
 * | `co-op`, `horror`, `open world` (any of the slice's tags) | a tag every pick must have |
 * | `under $20`, `below 15`, `free` | a price ceiling (free is 0) |
 * | `after 2012`, `since 2012`, `before 2010`, `2010 to 2014`, `2010s` | a release-year range |
 *
 * Anything else is reported back as not understood. Filters remove games before the shortlist, so
 * a filtered pick can never break one (the pipeline's `allowed` mask), and a game with an unknown
 * price or year fails any filter on it.
 */
import type { SliceGame } from '../engine/types';

export interface Filters {
  tags: string[];
  maxPrice: number | null;
  yearMin: number | null;
  yearMax: number | null;
}

export const NO_FILTERS: Filters = { tags: [], maxPrice: null, yearMin: null, yearMax: null };

export interface ParsedQuery {
  anchors: number[];
  filters: Filters;
  unresolved: string[];
}

/** Lower case, letters and digits only: "Co-op" and "co op" both become "coop". */
export const fold = (text: string): string =>
  text
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '');

const SYNONYMS: Record<string, string> = {
  coop: 'Co-op',
  cooperative: 'Co-op',
  singleplayer: 'Singleplayer',
  solo: 'Singleplayer',
  multiplayer: 'Multiplayer',
  scifi: 'Sci-fi',
  sciencefiction: 'Sci-fi',
  roguelite: 'Rogue-lite',
  roguelike: 'Rogue-like',
  shooter: 'Shooter',
  fps: 'FPS',
  rpg: 'RPG',
};

export function hasFilters(f: Filters): boolean {
  return f.tags.length > 0 || f.maxPrice !== null || f.yearMin !== null || f.yearMax !== null;
}

/** Does a game pass every filter? Unknown price or year fails a filter on it. */
export function passes(game: SliceGame, f: Filters): boolean {
  if (f.maxPrice !== null && (game.price === null || game.price > f.maxPrice)) return false;
  if ((f.yearMin !== null || f.yearMax !== null) && game.year === null) return false;
  if (f.yearMin !== null && game.year !== null && game.year < f.yearMin) return false;
  if (f.yearMax !== null && game.year !== null && game.year > f.yearMax) return false;
  if (f.tags.length) {
    const own = new Set(game.tags);
    for (const t of f.tags) if (!own.has(t)) return false;
  }
  return true;
}

/** The pipeline's mask, or null when nothing is filtered (every game allowed). */
export function allowedMask(games: SliceGame[], f: Filters): boolean[] | null {
  return hasFilters(f) ? games.map((g) => passes(g, f)) : null;
}

/** Filters in plain words, one per chip. */
export function describe(f: Filters): string[] {
  const out = f.tags.map((t) => t);
  if (f.maxPrice !== null) out.push(f.maxPrice === 0 ? 'Free' : `Under $${f.maxPrice % 1 ? f.maxPrice.toFixed(2) : f.maxPrice}`);
  if (f.yearMin !== null && f.yearMax !== null) out.push(f.yearMin === f.yearMax ? `${f.yearMin}` : `${f.yearMin} to ${f.yearMax}`);
  else if (f.yearMin !== null) out.push(`${f.yearMin} or later`);
  else if (f.yearMax !== null) out.push(`${f.yearMax} or earlier`);
  return out;
}

/** The game a phrase names: exact title, then a title starting with it, then containing it; ties to the most played. */
export function findGame(phrase: string, games: SliceGame[]): number | null {
  const want = fold(phrase);
  if (want.length < 2) return null;
  let best: [number, number] | null = null; // [index, quality] — higher is better
  games.forEach((g, i) => {
    const t = fold(g.title);
    const quality = t === want ? 3 : t.startsWith(want) ? 2 : want.length >= 4 && t.includes(want) ? 1 : 0;
    if (!quality) return;
    if (!best || quality > best[1] || (quality === best[1] && g.plays > games[best[0]].plays)) best = [i, quality];
  });
  return best ? best[0] : null;
}

function tagFor(phrase: string, vocabulary: Map<string, string>): string | null {
  const key = fold(phrase);
  return vocabulary.get(key) ?? (SYNONYMS[key] && vocabulary.has(fold(SYNONYMS[key])) ? SYNONYMS[key] : null);
}

const PRICE = /^(?:under|below|less than|cheaper than|max|up to|<)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:dollars|usd)?$/;
const AFTER = /^(after|since|from)\s+((?:19|20)\d\d)$/;
const BEFORE = /^(before|until|up to|through)\s+((?:19|20)\d\d)$/;
const RANGE = /^((?:19|20)\d\d)\s*(?:-|to|–|—)\s*((?:19|20)\d\d)$/;
const DECADE = /^((?:19|20)\d)0s$/;
const LIKE = /^(?:games?\s+)?(?:like|similar to)\s+(.+)$/;

/** Is `phrase` exactly a title (after an optional "like"), so separators inside it must not split it? */
function isTitle(phrase: string, games: SliceGame[]): boolean {
  const c = phrase.trim().toLowerCase();
  const m = c.match(LIKE);
  const name = fold(m ? m[1] : c);
  return name.length > 1 && games.some((g) => fold(g.title) === name);
}

/** Split on commas, semicolons, "and" and "with", but keep titles like "Papers, Please" whole. */
export function clauses(text: string, games: SliceGame[]): string[] {
  const parts = text.split(/(,|;|\band\b|\bwith\b)/i);
  const out: string[] = [];
  let i = 0;
  while (i < parts.length) {
    let taken = false;
    for (let j = Math.min(parts.length - 1, i + 4); j > i; j -= 2) {
      const joined = parts.slice(i, j + 1).join('');
      if (isTitle(joined, games)) {
        out.push(joined.trim());
        i = j + 2;
        taken = true;
        break;
      }
    }
    if (!taken) {
      if (parts[i].trim()) out.push(parts[i].trim());
      i += 2;
    }
  }
  return out;
}

export function parseQuery(text: string, games: SliceGame[]): ParsedQuery {
  const vocabulary = new Map<string, string>();
  for (const g of games) for (const t of g.tags) vocabulary.set(fold(t), t);
  const anchors: number[] = [];
  const tags: string[] = [];
  const unresolved: string[] = [];
  const f: Filters = { ...NO_FILTERS, tags };
  for (const raw of clauses(text, games)) {
    const c = raw.toLowerCase().replace(/\s+/g, ' ');
    let m: RegExpMatchArray | null;
    if ((m = c.match(LIKE))) {
      const i = findGame(m[1], games);
      if (i === null) unresolved.push(raw);
      else if (!anchors.includes(i)) anchors.push(i);
    } else if (c === 'free' || c === 'free to play' || c === 'f2p') {
      f.maxPrice = 0;
    } else if ((m = c.match(PRICE))) {
      f.maxPrice = Number(m[1]);
    } else if ((m = c.match(AFTER))) {
      f.yearMin = Number(m[2]) + (m[1] === 'after' ? 1 : 0);
    } else if ((m = c.match(BEFORE))) {
      f.yearMax = Number(m[2]) - (m[1] === 'before' ? 1 : 0);
    } else if ((m = c.match(RANGE))) {
      f.yearMin = Math.min(Number(m[1]), Number(m[2]));
      f.yearMax = Math.max(Number(m[1]), Number(m[2]));
    } else if ((m = c.match(DECADE))) {
      f.yearMin = Number(`${m[1]}0`);
      f.yearMax = f.yearMin + 9;
    } else if (/^(?:19|20)\d\d$/.test(c)) {
      f.yearMin = f.yearMax = Number(c);
    } else {
      const tag = tagFor(c, vocabulary);
      if (tag) {
        if (!tags.includes(tag)) tags.push(tag);
        continue;
      }
      const i = findGame(c, games);
      if (i !== null && fold(games[i].title) === fold(c)) {
        if (!anchors.includes(i)) anchors.push(i);
      } else unresolved.push(raw);
    }
  }
  return { anchors, filters: f, unresolved };
}

/** Merge new filters into old ones (new values win, tags accumulate). */
export function merge(a: Filters, b: Filters): Filters {
  return {
    tags: [...a.tags, ...b.tags.filter((t) => !a.tags.includes(t))],
    maxPrice: b.maxPrice ?? a.maxPrice,
    yearMin: b.yearMin ?? a.yearMin,
    yearMax: b.yearMax ?? a.yearMax,
  };
}
