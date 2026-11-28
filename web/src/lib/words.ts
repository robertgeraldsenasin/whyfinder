/**
 * Grounded words: the numbered facts for one pick, the sentences built straight from them, and the
 * claim checker every sentence has to pass. Twins of `facts` and `template` in
 * src/whyfinder/rag/generate.py and `check` in src/whyfinder/rag/claims.py; both sides are held to
 * the shared cases in __fixtures__/claims.json. Evidence keeps the API's snake_case keys, so a claim
 * here has the same JSON as a claim from POST /explain.
 */
import type { PickExplanation } from '../engine/engine';
import type { SliceGame } from '../engine/types';
import type { Evidence as Reviews, Quote } from './evidence';

export const MAX_CLAIMS = 3;
export const MAX_WORDS = 60;
export const MAX_QUOTE_WORDS = 25;
export const TOP = 5;
const QUOTES = 2;

export interface AttributionRef {
  type: 'attribution';
  game_id: string;
  share: number;
}
export interface ReviewRef {
  type: 'review';
  chunk_id: string;
  quote: string;
}
export interface CounterfactualRef {
  type: 'counterfactual';
  removed_game_ids: string[];
}
export type Ref = AttributionRef | ReviewRef | CounterfactualRef;

export interface Claim {
  text: string;
  evidence: Ref[];
}

/** What a pick's claims may rest on. */
export interface Source {
  pickTitle: string;
  /** [game_id, title, share], largest first: every liked game. */
  attributions: [string, string, number][];
  /** chunk_id → text: the review passages retrieved for the pick. */
  chunks: Record<string, string>;
  /** The counterfactual set, as game IDs. */
  removed: string[];
  catalogue: string[];
}

/** The facts for one pick, in the order a prompt lists them. */
export interface Pack {
  pickTitle: string;
  attributions: [string, string, number][];
  removed: [string, string][];
  /** [chunk_id, aspect, text] */
  quotes: [string, string, string][];
}

export interface Fact {
  id: string;
  line: string;
  evidence: Ref;
}

/** Python's round(): a half goes to the even neighbour, so 62.5 → 62 and 63.5 → 64. */
export function roundHalfEven(x: number): number {
  return Math.abs(x - Math.trunc(x)) === 0.5 ? 2 * Math.round(x / 2) : Math.round(x);
}

const words = (text: string): string[] => text.split(/\s+/).filter(Boolean);
const percent = (share: number): number => roundHalfEven(share * 100);

/**
 * The citable facts, with IDs: A for attributions, C for the counterfactual, Q for quotes. Quotes
 * holding a straight double quote or a backslash are left out, as in Python, where they cannot be
 * pinned inside a JSON string.
 */
export function facts(pack: Pack): Fact[] {
  const out: Fact[] = [];
  pack.attributions
    .slice(0, TOP)
    .filter(([, , share]) => share > 0)
    .forEach(([game_id, title, share], n) => {
      const line = `${title} counted for ${percent(share)}% of the score`;
      out.push({ id: `A${n + 1}`, line, evidence: { type: 'attribution', game_id, share } });
    });
  if (pack.removed.length > 0) {
    const names = pack.removed.map(([, title]) => title).join(' and ');
    const line = `without ${names} in the list, ${pack.pickTitle} would drop out of the picks`;
    const removed_game_ids = pack.removed.map(([id]) => id);
    out.push({ id: 'C1', line, evidence: { type: 'counterfactual', removed_game_ids } });
  }
  pack.quotes
    .filter(([, , text]) => !text.includes('"') && !text.includes('\\'))
    .forEach(([chunk_id, aspect, text], n) => {
      const line = `a player of ${pack.pickTitle}, on ${aspect}: “${text}”`;
      out.push({ id: `Q${n + 1}`, line, evidence: { type: 'review', chunk_id, quote: text } });
    });
  return out;
}

/** Sentences built straight from the facts: the top attribution, the second when it carries at
 * least 10%, then quotes, within the claim and word limits. */
export function template(pack: Pack): Claim[] {
  const claims: Claim[] = [];
  const positive = pack.attributions.filter(([, , share]) => share > 0);
  for (const [n, [game_id, title, share]] of positive.slice(0, 2).entries()) {
    if (n === 1 && share < 0.1) break;
    const pct = `${percent(share)}%`;
    const text = n === 0 ? `${title} is the biggest driver of this pick (${pct}).` : `${title} adds ${pct}.`;
    claims.push({ text, evidence: [{ type: 'attribution', game_id, share }] });
  }
  for (const [chunk_id, aspect, quote] of pack.quotes) {
    claims.push({
      text: `Players of ${pack.pickTitle} mention ${aspect}: "${quote}"`,
      evidence: [{ type: 'review', chunk_id, quote }],
    });
  }
  const out: Claim[] = [];
  let total = 0;
  for (const claim of claims) {
    const n = words(claim.text).length;
    if (out.length === MAX_CLAIMS || total + n > MAX_WORDS) break;
    out.push(claim);
    total += n;
  }
  return out;
}

/** A quote is a span of the chunk (whitespace normalised), 1 to 25 words long. */
export function isVerbatim(quote: string, text: string): boolean {
  const q = words(quote);
  return q.length > 0 && q.length <= MAX_QUOTE_WORDS && words(text).join(' ').includes(q.join(' '));
}

// Python's \w for str: letters, numbers and the underscore.
const W = '[\\p{L}\\p{N}_]';
const escape = (s: string): string => s.replace(/[\^$\\.*+?()[\]{}|/]/g, '\\$&');
const named = (title: string, flags = 'u'): RegExp => new RegExp(`(?<!${W})${escape(title)}(?!${W})`, flags);

/** `text` without the trademark signs players rarely type, whitespace normalised. */
export function bare(text: string): string {
  return words(text.replace(/[\u00ae\u2122\u00a9]/g, '')).join(' ');
}

/** The sentence names the title, with or without its trademark signs. */
export function names(text: string, title: string): boolean {
  return text.includes(title) || bare(text).includes(bare(title));
}

/** Catalogue titles a sentence names, outside its quotes, that are not allowed, with or without
 * their trademark signs. Allowed titles are blanked first, longest first, so "Portal 2" never
 * reads as "Portal". */
export function unlistedGames(text: string, quotes: string[], catalogue: string[], allowed: Set<string>): string[] {
  let rest = text;
  for (const quote of quotes) rest = rest.replaceAll(quote, ' ');
  rest = bare(rest);
  const blank = [...new Set([...allowed].map(bare))].sort((a, b) => b.length - a.length);
  for (const title of blank) rest = rest.replace(named(title, 'gu'), ' ');
  return catalogue.filter((title) => !allowed.has(title) && bare(title).length > 3 && named(bare(title)).test(rest));
}

/**
 * Every reason the claims fail FR-17; empty when they all pass. The rules, in Python's order:
 * attributions must be among the top five with the computed share and named in the sentence, any
 * percentage within a point of a cited share; quotes must come from a retrieved chunk, verbatim,
 * and sit in the sentence; a counterfactual must be the computed set; no game outside the pick and
 * the history; at most three claims and sixty words.
 */
export function check(claims: Claim[], source: Source): string[] {
  const reasons: string[] = [];
  if (claims.length > MAX_CLAIMS) reasons.push(`more than ${MAX_CLAIMS} claims`);
  const total = claims.reduce((s, c) => s + words(c.text).length, 0);
  if (total > MAX_WORDS) reasons.push(`${total} words; the limit is ${MAX_WORDS}`);
  const top = new Map(source.attributions.slice(0, TOP).map(([id, title, share]) => [id, { title, share }]));
  const allowed = new Set([source.pickTitle, ...source.attributions.map(([, title]) => title)]);
  const removed = new Set(source.removed);
  for (const claim of claims) {
    if (claim.evidence.length === 0) {
      reasons.push(`no evidence for: ${claim.text}`);
      continue;
    }
    const quotes = claim.evidence.flatMap((e) => (e.type === 'review' ? [e.quote] : []));
    for (const game of unlistedGames(claim.text, quotes, source.catalogue, allowed)) {
      reasons.push(`names a game outside the pick and the history: ${game}`);
    }
    const cited: number[] = [];
    for (const e of claim.evidence) {
      if (e.type === 'attribution') {
        const fact = top.get(e.game_id);
        if (!fact) {
          reasons.push(`cites a game that is not among the top ${TOP}: ${e.game_id}`);
          continue;
        }
        if (Math.abs(fact.share - e.share) > 0.005) {
          reasons.push(`wrong share for ${fact.title}: ${e.share.toFixed(3)}, not ${fact.share.toFixed(3)}`);
        } else if (!names(claim.text, fact.title)) {
          reasons.push(`cites ${fact.title} without naming it`);
        }
        cited.push(fact.share);
      } else if (e.type === 'review') {
        const text = Object.hasOwn(source.chunks, e.chunk_id) ? source.chunks[e.chunk_id] : undefined;
        if (text === undefined) reasons.push(`cites a review chunk not retrieved for this pick: ${e.chunk_id}`);
        else if (!isVerbatim(e.quote, text)) reasons.push(`the quote is not a verbatim span of ${e.chunk_id}`);
        else if (!claim.text.includes(e.quote)) reasons.push(`the sentence does not carry its quote from ${e.chunk_id}`);
      } else {
        const set = new Set(e.removed_game_ids);
        if (set.size !== removed.size || [...set].some((id) => !removed.has(id))) {
          reasons.push('the counterfactual set is not the computed one');
        }
      }
    }
    let outside = claim.text;
    for (const quote of quotes) outside = outside.replaceAll(quote, ' ');
    for (const m of outside.matchAll(/(\d+(?:\.\d+)?)\s*%/g)) {
      const stated = Number(m[1]) / 100;
      if (!cited.some((c) => Math.abs(stated - c) <= 0.01 + 1e-9)) reasons.push(`${m[0]} matches no cited share`);
    }
  }
  return reasons;
}

/** What the pick shares with a liked game: common tags in the pick's order, then the words both
 * games' players use (the API's `aspects`). */
export function aspects(pick: SliceGame, liked: SliceGame, reviews: Reviews | null, limit = 4): string[] {
  const theirs = new Set(liked.tags);
  const shared = pick.tags.filter((t) => theirs.has(t));
  const terms = (g: SliceGame) => reviews?.games[String(g.id)]?.terms.map(([t]) => t) ?? [];
  const spoken = new Set(terms(liked));
  for (const w of terms(pick)) if (spoken.has(w) && !shared.includes(w)) shared.push(w);
  return shared.slice(0, limit);
}

/** For each aspect, the first of the pick's quotes that names it as a whole word, any case; distinct
 * quotes, at most two. The API ranks the pick's passages with BM25 and dense retrieval; the static
 * demo has no index, so it takes the export's order. Chunk IDs are `<game id>:<quote number>`. */
export function quotesFor(gameId: number, quotes: Quote[], wanted: string[], limit = QUOTES): [string, string, string][] {
  const out: [string, string, string][] = [];
  const used = new Set<number>();
  for (const aspect of wanted) {
    const re = new RegExp(`(?<!${W})${escape(aspect)}(?!${W})`, 'iu');
    const k = quotes.findIndex((q, i) => !used.has(i) && re.test(q.text));
    if (k < 0) continue;
    used.add(k);
    out.push([`${gameId}:${k}`, aspect, quotes[k].text]);
    if (out.length === limit) break;
  }
  return out;
}

/** The pack and the checker's source for one explained pick, as the API's `grounding.facts` builds
 * them: shares of the summed absolute contributions, quotes on what the pick shares with its
 * strongest positive reason. */
export function ground(e: PickExplanation, games: SliceGame[], reviews: Reviews | null): { pack: Pack; source: Source } {
  const total = e.attributions.reduce((s, a) => s + Math.abs(a.total), 0) || 1;
  const attributions = e.attributions.map((a): [string, string, number] => [String(games[a.game].id), games[a.game].title, a.total / total]);
  const pick = games[e.pick];
  const strongest = e.attributions.find((a) => a.total > 0);
  const ev = reviews?.games[String(pick.id)];
  const quotes = strongest && ev ? quotesFor(pick.id, ev.quotes, aspects(pick, games[strongest.game], reviews)) : [];
  const removed = e.counterfactual.removed.map((j): [string, string] => [String(games[j].id), games[j].title]);
  const chunks: Record<string, string> = {};
  ev?.quotes.forEach((q, k) => (chunks[`${pick.id}:${k}`] = q.text));
  return {
    pack: { pickTitle: pick.title, attributions, removed, quotes },
    source: { pickTitle: pick.title, attributions, chunks, removed: removed.map(([id]) => id), catalogue: games.map((g) => g.title) },
  };
}

/**
 * Three sentences with the slips free models made in the generation study (ADR-0009), written
 * from the same facts: a percentage that is not the share, the recommended game praised in place
 * of the liked one next to a game from outside the facts, and a quote retold rather than copied
 * (or, without a quote, a counterfactual that is not the computed set). `stranger` is a catalogue
 * title outside the pick and the history.
 */
export function slips(pack: Pack, stranger: string): Claim[] {
  const listed = facts(pack);
  const a1 = listed.find((f) => f.id === 'A1')?.evidence;
  if (a1?.type !== 'attribution') return [];
  const title = pack.attributions.find(([id]) => id === a1.game_id)?.[1] ?? a1.game_id;
  const out: Claim[] = [
    { text: `${title} counted for ${percent(a1.share) + 9}% of the score.`, evidence: [a1] },
    { text: `${pack.pickTitle} plays a lot like ${stranger}.`, evidence: [a1] },
  ];
  const q = listed.find((f) => f.evidence.type === 'review' && words((f.evidence as ReviewRef).quote).length >= 4);
  if (q && q.evidence.type === 'review') {
    const w = words(q.evidence.quote);
    const retold = [...w.slice(0, 1), ...w.slice(2)].join(' ');
    out.push({ text: `Players say "${retold}"`, evidence: [{ ...q.evidence, quote: retold }] });
  } else {
    const ids = [...new Set([...pack.removed.map(([id]) => id), ...pack.attributions.slice(0, 2).map(([id]) => id)])];
    const off = ids.length > pack.removed.length ? ids : ids.slice(0, -1);
    const names = off.map((id) => pack.attributions.find(([g]) => g === id)?.[1] ?? id);
    out.push({
      text: `Without ${names.join(' and ')}, ${pack.pickTitle} would drop out.`,
      evidence: [{ type: 'counterfactual', removed_game_ids: off }],
    });
  }
  return out;
}
