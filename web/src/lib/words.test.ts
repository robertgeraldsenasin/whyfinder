import { readFileSync } from 'node:fs';
import { beforeAll, describe, expect, it } from 'vitest';
import { Engine, type Explained } from '../engine/engine';
import type { ModelFile, Slice } from '../engine/types';
import type { Evidence as Reviews } from './evidence';
import {
  aspects,
  bare,
  check,
  type Claim,
  facts,
  ground,
  isVerbatim,
  names,
  type Pack,
  quotesFor,
  roundHalfEven,
  slips,
  type Source,
  template,
  unlistedGames,
} from './words';

const read = <T>(path: string): T => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8')) as T;
const slice = read<Slice>('../../public/data/demo-slice.json');
const reviews = read<Reviews>('../../public/data/reviews.json');
const games = slice.games;
const index = (title: string) => games.findIndex((g) => g.title === title);

interface Shared {
  source: { pick_title: string; attributions: [string, string, number][]; chunks: Record<string, string>; removed: string[]; catalogue: string[] };
  cases: { name: string; claims: Claim[]; reasons: string[] }[];
  packs: {
    name: string;
    pack: { pick_title: string; attributions: [string, string, number][]; removed: [string, string][]; quotes: [string, string, string][] };
    facts: [string, string][];
    template: Claim[];
  }[];
}
const shared = read<Shared>('./__fixtures__/claims.json');
const source: Source = {
  pickTitle: shared.source.pick_title,
  attributions: shared.source.attributions,
  chunks: shared.source.chunks,
  removed: shared.source.removed,
  catalogue: shared.source.catalogue,
};

describe('the shared cases (src/whyfinder/rag)', () => {
  it.each(shared.cases.map((c) => [c.name, c] as const))('%s: same reasons as the Python checker', (_, c) => {
    expect(check(c.claims, source)).toEqual(c.reasons);
  });

  it.each(shared.packs.map((p) => [p.name, p] as const))('%s: same facts and sentences as Python', (_, p) => {
    const pack: Pack = { pickTitle: p.pack.pick_title, attributions: p.pack.attributions, removed: p.pack.removed, quotes: p.pack.quotes };
    expect(facts(pack).map((f) => [f.id, f.line])).toEqual(p.facts);
    expect(template(pack)).toEqual(p.template);
  });
});

describe('the pieces', () => {
  it('rounds halves to even, like Python', () => {
    expect([62.5, 63.5, 12.5, -2.5, 41.2, 41.7].map(roundHalfEven)).toEqual([62, 64, 12, -2, 41, 42]);
  });

  it('takes a quote as verbatim only within 25 words, whitespace aside', () => {
    expect(isVerbatim('so   different', 'The classes are so different.')).toBe(true);
    expect(isVerbatim('', 'anything')).toBe(false);
    expect(isVerbatim('so different classes', 'The classes are so different.')).toBe(false);
    const long = Array.from({ length: 26 }, (_, i) => `w${i}`).join(' ');
    expect(isVerbatim(long, long)).toBe(false);
  });

  it('reads titles as whole words and lets an allowed title shadow a shorter one', () => {
    const catalogue = ['Portal', 'Portal 2', 'Rust', 'Thief'];
    expect(unlistedGames('Portal 2 and Portal', [], catalogue, new Set(['Portal 2']))).toEqual(['Portal']);
    expect(unlistedGames('Portal 2 again', [], catalogue, new Set(['Portal 2']))).toEqual([]);
    expect(unlistedGames('Thieves and rusty keys', [], catalogue, new Set())).toEqual([]);
    expect(unlistedGames('as a "Thief" would', ['Thief'], catalogue, new Set())).toEqual([]);
    expect(unlistedGames('Café (Deluxe)', [], ['Café (Deluxe)'], new Set())).toEqual(['Café (Deluxe)']);
  });

  it('reads titles with or without their trademark signs', () => {
    expect(bare('BioShock\u00ae 2:  Total War\u2122')).toBe('BioShock 2: Total War');
    expect(names('BioShock 2 drives it.', 'BioShock\u00ae 2')).toBe(true);
    expect(names('BioShock drives it.', 'BioShock\u00ae 2')).toBe(false);
    expect(unlistedGames('Like Call of Duty: Black Ops.', [], ['Call of Duty\u00ae: Black Ops'], new Set())).toEqual(['Call of Duty\u00ae: Black Ops']);
    expect(unlistedGames('BioShock 2 again.', [], ['BioShock\u00ae 2'], new Set(['BioShock\u00ae 2']))).toEqual([]);
  });

  it('does not treat chunk IDs that look like object keys as retrieved', () => {
    const claim: Claim = { text: 'Players say "x y"', evidence: [{ type: 'review', chunk_id: 'constructor', quote: 'x y' }] };
    expect(check([claim], source)).toEqual(['cites a review chunk not retrieved for this pick: constructor']);
  });

  it('finds aspects from shared tags first, then shared review words', () => {
    const a = aspects(games[index('Portal 2')], games[index('Half-Life 2')], reviews);
    const shared = games[index('Portal 2')].tags.filter((t) => games[index('Half-Life 2')].tags.includes(t));
    expect(a.slice(0, Math.min(4, shared.length))).toEqual(shared.slice(0, 4));
    expect(a.length).toBeLessThanOrEqual(4);
    expect(aspects(games[0], games[0], null, 2)).toEqual(games[0].tags.slice(0, 2));
  });

  it('quotes a review only when it names the aspect, each review once', () => {
    const quotes = [
      { text: 'Great COOP night.', hours: 1, year: 2016, also: [] },
      { text: 'co-op with friends is the best', hours: 2, year: 2016, also: [] },
      { text: 'The co-op campaign is short.', hours: 3, year: 2017, also: [] },
    ];
    expect(quotesFor(7, quotes, ['Co-op', 'co-op', 'zombies'])).toEqual([
      ['7:1', 'Co-op', 'co-op with friends is the best'],
      ['7:2', 'co-op', 'The co-op campaign is short.'],
    ]);
    expect(quotesFor(7, quotes, ['zombies'])).toEqual([]);
  });
});

describe('on the demo engine', () => {
  let runs: Explained[];
  beforeAll(() => {
    const engine = new Engine(slice, read<ModelFile>('../../public/data/model.json'));
    const histories = [
      ['Portal 2', 'Borderlands 2'],
      ['FTL: Faster Than Light', 'The Binding of Isaac', 'XCOM: Enemy Unknown'],
      ['Starbound', "Garry's Mod", 'Rust'],
    ];
    runs = histories.map((titles) =>
      engine.explain(titles.map(index).filter((j) => j >= 0).map((j, k) => [j, engine.weight(20 + 15 * k)])),
    );
  });

  it('builds sentences for every pick that pass the checker', () => {
    let quoted = 0;
    for (const run of runs) {
      for (const e of run.explanations) {
        const { pack, source: src } = ground(e, games, reviews);
        const claims = template(pack);
        expect(claims.length).toBeGreaterThan(0);
        expect(check(claims, src)).toEqual([]);
        quoted += pack.quotes.length;
      }
    }
    expect(quoted).toBeGreaterThan(0);
  });

  it('numbers facts that match the exact shares', () => {
    const e = runs[0].explanations[0];
    const { pack } = ground(e, games, reviews);
    const total = e.attributions.reduce((s, a) => s + Math.abs(a.total), 0);
    const listed = facts(pack).filter((f) => f.id.startsWith('A'));
    const positive = e.attributions.slice(0, 5).filter((a) => a.total > 0);
    expect(listed.map((f) => (f.evidence.type === 'attribution' ? f.evidence.share : NaN))).toEqual(positive.map((a) => a.total / total));
    expect(facts(pack).some((f) => f.id === 'C1')).toBe(e.counterfactual.removed.length > 0);
  });

  it('catches every slip a free model made, sentence by sentence', () => {
    for (const run of runs) {
      const hist = new Set(run.history.map(([j]) => j));
      for (const e of run.explanations) {
        const { pack, source: src } = ground(e, games, reviews);
        const stranger = games.find((g, i) => !hist.has(i) && i !== e.pick && g.title.length > 3)!.title;
        const bad = slips(pack, stranger);
        expect(bad).toHaveLength(3);
        for (const claim of bad) expect(check([claim], src)).not.toEqual([]);
        expect(check(bad, src)).toContain(`names a game outside the pick and the history: ${stranger}`);
      }
    }
  });

  it('works without the review export: no quotes, still faithful', () => {
    const e = runs[1].explanations[0];
    const { pack, source: src } = ground(e, games, null);
    expect(pack.quotes).toEqual([]);
    expect(check(template(pack), src)).toEqual([]);
    expect(slips(pack, 'Counter-Strike: Global Offensive')).toHaveLength(3);
  });
});
