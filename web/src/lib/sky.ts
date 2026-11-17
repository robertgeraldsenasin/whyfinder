/**
 * Closeness and its colours (ADR-0017).
 *
 * Closeness is how near a game sits to your taste: c = sqrt(s / s_max), where s is the game's
 * score and s_max the best score among games you do not own. The square root spreads the many
 * weak matches apart and keeps the strong ones distinct, so colour changes most where people look.
 * Colours are interpolated in OKLab so equal steps in c look like equal steps in colour.
 */

export type Palette = 'gold-violet' | 'gold' | 'spectrum';

export const PALETTES: { id: Palette; name: string; description: string }[] = [
  { id: 'gold-violet', name: 'Gold and violet', description: 'Violet for distant games, gold for the closest.' },
  { id: 'gold', name: 'Gold', description: 'Dim bronze for distant games, bright gold for the closest.' },
  { id: 'spectrum', name: 'Star temperature', description: 'Like real stars: red for distant, blue-white for the closest.' },
];

/** Colour stops from distant (0) to closest (1). */
const STOPS: Record<Palette, [number, string][]> = {
  'gold-violet': [
    [0, '#3b338f'],
    [0.3, '#7d5fe6'],
    [0.5, '#c7b6ff'],
    [0.66, '#fff4dc'],
    [0.84, '#ffd877'],
    [1, '#f2b632'],
  ],
  gold: [
    [0, '#5c4622'],
    [0.4, '#a8781a'],
    [0.75, '#f2c14e'],
    [1, '#ffe7a6'],
  ],
  spectrum: [
    [0, '#d9503a'],
    [0.28, '#ff9a4d'],
    [0.52, '#ffe08a'],
    [0.76, '#f5f2ff'],
    [1, '#8fbaff'],
  ],
};

export interface Tier {
  min: number;
  name: string;
  plain: string;
}

/** Named bands of closeness, closest first. */
export const TIERS: Tier[] = [
  { min: 0.9, name: 'Twin star', plain: 'about as close to your taste as a game gets here' },
  { min: 0.7, name: 'Close orbit', plain: 'close to your taste' },
  { min: 0.5, name: 'Same constellation', plain: 'shares a lot with your games' },
  { min: 0.3, name: 'Neighbouring sky', plain: 'some overlap with your games' },
  { min: 0, name: 'Distant light', plain: 'little overlap with your games' },
];

export function tier(c: number): Tier {
  return TIERS.find((t) => c >= t.min) ?? TIERS[TIERS.length - 1];
}

/** Closeness for every game; owned games get NaN. */
export function closeness(scores: ArrayLike<number>, owned: Iterable<number>): Float32Array {
  const skip = new Set(owned);
  let best = 0;
  for (let i = 0; i < scores.length; i++) {
    const s = scores[i];
    if (!skip.has(i) && Number.isFinite(s) && s > best) best = s;
  }
  const out = new Float32Array(scores.length);
  for (let i = 0; i < scores.length; i++) {
    const s = scores[i];
    if (skip.has(i)) out[i] = Number.NaN;
    else out[i] = best > 0 && Number.isFinite(s) && s > 0 ? Math.sqrt(Math.min(1, s / best)) : 0;
  }
  return out;
}

type Lab = [number, number, number];

const toLinear = (c: number): number => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const toGamma = (c: number): number => (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055);

export function hexToRgb(hex: string): [number, number, number] {
  const n = Number.parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function rgbToHex([r, g, b]: [number, number, number]): string {
  const c = (x: number) => Math.round(Math.min(255, Math.max(0, x))).toString(16).padStart(2, '0');
  return `#${c(r)}${c(g)}${c(b)}`;
}

export function toOklab(hex: string): Lab {
  const [r, g, b] = hexToRgb(hex).map((x) => toLinear(x / 255));
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

export function fromOklab([L, a, b]: Lab): string {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const rgb: [number, number, number] = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
  return rgbToHex(rgb.map((x) => toGamma(Math.min(1, Math.max(0, x))) * 255) as [number, number, number]);
}

const labStops = new Map<Palette, [number, Lab][]>();

/** The colour for closeness c in a palette. */
export function colorAt(palette: Palette, c: number): string {
  let stops = labStops.get(palette);
  if (!stops) {
    stops = STOPS[palette].map(([t, hex]) => [t, toOklab(hex)]);
    labStops.set(palette, stops);
  }
  const x = Math.min(1, Math.max(0, Number.isFinite(c) ? c : 0));
  let k = 1;
  while (k < stops.length - 1 && stops[k][0] < x) k++;
  const [t0, a] = stops[k - 1];
  const [t1, b] = stops[k];
  const f = t1 > t0 ? (x - t0) / (t1 - t0) : 0;
  return fromOklab([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f]);
}

/** A CSS gradient of a palette, distant to closest, for legends and the settings preview. */
export function gradient(palette: Palette, direction = 'to right'): string {
  const steps = Array.from({ length: 9 }, (_, k) => `${colorAt(palette, k / 8)} ${(k / 8) * 100}%`);
  return `linear-gradient(${direction}, ${steps.join(', ')})`;
}
