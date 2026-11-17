export const pct = (x: number, digits = 0): string => `${(x * 100).toFixed(digits)}%`;

export const int = (x: number): string => Math.round(x).toLocaleString('en-US');

export const ms = (x: number): string => (x < 10 ? `${x.toFixed(1)} ms` : `${Math.round(x)} ms`);

export const num = (x: number, digits = 4): string => {
  if (x === 0) return '0';
  const a = Math.abs(x);
  if (a >= 1000 || a < 1e-3) return x.toExponential(2);
  return x.toFixed(digits);
};

export const rank = (r: number): string => String(r + 1).padStart(2, '0');

export const price = (p: number | null): string => (p === null ? 'price n/a' : p === 0 ? 'Free' : `$${p.toFixed(2)}`);

export function list(names: string[]): string {
  if (names.length <= 1) return names.join('');
  if (names.length === 2) return `${names[0]} and ${names[1]}`;
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

const GITHUB = 'https://github.com/robertgeraldsenasin/whyfinder';
export const source = (path: string): string => `${GITHUB}/blob/main/${path}`;
export const repo = GITHUB;
