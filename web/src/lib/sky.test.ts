import { describe, expect, it } from 'vitest';
import { closeness, colorAt, fromOklab, gradient, migratePalette, PALETTES, tier, TIERS, toOklab } from './sky';

describe('closeness', () => {
  it('is the square root of the score relative to the best game you do not own', () => {
    const c = closeness([9, 4, 1, 0, -2, 100], [5]);
    expect(Array.from(c.slice(0, 5))).toEqual([1, 2 / 3, 1 / 3, 0, 0].map((x) => Math.fround(x)));
    expect(Number.isNaN(c[5])).toBe(true);
  });

  it('is zero everywhere when nothing scores', () => {
    expect(Array.from(closeness([0, 0, -1], []))).toEqual([0, 0, 0]);
  });

  it('ignores non-finite scores', () => {
    expect(Array.from(closeness([Number.NaN, 4, Number.POSITIVE_INFINITY], []))).toEqual([0, 1, 0]);
  });
});

describe('tiers', () => {
  it('name every band, closest first', () => {
    expect(tier(1).name).toBe('Twin star');
    expect(tier(0.9).name).toBe('Twin star');
    expect(tier(0.89).name).toBe('Close orbit');
    expect(tier(0.5).name).toBe('Same constellation');
    expect(tier(0.3).name).toBe('Neighbouring sky');
    expect(tier(0).name).toBe('Distant light');
    expect(tier(-1).name).toBe('Distant light');
    expect(TIERS.map((t) => t.min)).toEqual([...TIERS.map((t) => t.min)].sort((a, b) => b - a));
  });
});

describe('saved palettes', () => {
  it('carry over from Starfall and drop unknown values', () => {
    expect(migratePalette('gold-violet')).toBe('crimson-violet');
    expect(migratePalette('gold')).toBe('crimson');
    expect(migratePalette('spectrum')).toBe('spectrum');
    expect(migratePalette('crimson')).toBe('crimson');
    expect(migratePalette('neon')).toBeNull();
    expect(migratePalette(undefined)).toBeNull();
  });
});

describe('colours', () => {
  it('round-trip through OKLab', () => {
    for (const hex of ['#000000', '#ffffff', '#d1173a', '#7b4dff', '#0b0710']) {
      expect(fromOklab(toOklab(hex))).toBe(hex);
    }
  });

  it('hit the stops exactly and clamp outside [0, 1]', () => {
    expect(colorAt('crimson-violet', 0)).toBe('#2b2166');
    expect(colorAt('crimson-violet', 1)).toBe('#ff1f45');
    expect(colorAt('crimson', 2)).toBe(colorAt('crimson', 1));
    expect(colorAt('spectrum', Number.NaN)).toBe(colorAt('spectrum', 0));
  });

  it('get lighter as games get closer in the crimson palette', () => {
    const lightness = Array.from({ length: 11 }, (_, k) => toOklab(colorAt('crimson', k / 10))[0]);
    for (let k = 1; k < lightness.length; k++) expect(lightness[k]).toBeGreaterThan(lightness[k - 1]);
  });

  it('build a legend gradient for every palette', () => {
    for (const p of PALETTES) expect(gradient(p.id)).toMatch(/^linear-gradient\(to right, #[0-9a-f]{6} 0%/);
  });
});

import { studio } from './format';

describe('studio names', () => {
  it('drop platform notes and repeats', () => {
    expect(studio('Firaxis,Feral Interactive (Mac),Feral Interactive (Linux)')).toBe('Firaxis, Feral Interactive');
    expect(studio(null)).toBe('');
    expect(studio('Valve')).toBe('Valve');
  });
});
