/**
 * The glass-box blend M = β·B/c_B + (1−β)·Π/c_Π and additive scoring s = Σ_j x_j·M_j·.
 * Twin of src/whyfinder/core/blend.py.
 */

/** x = 1 + α·log(1 + hours/ε). */
export function confidence(hours: number, alpha: number, eps: number): number {
  if (alpha < 0 || !(eps > 0)) throw new Error('need alpha ≥ 0 and eps > 0');
  return 1 + alpha * Math.log1p(hours / eps);
}

/** Nearest-rank q-quantile of |W| over non-zero off-diagonal entries (1 if none). */
export function scaleConstant(W: Float64Array, n: number, q = 0.99): number {
  if (!(q > 0 && q <= 1)) throw new Error('q must be in (0, 1]');
  const values: number[] = [];
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      if (i === j) continue;
      const a = Math.abs(W[i * n + j]);
      if (a > 0) values.push(a);
    }
  }
  if (values.length === 0) return 1;
  values.sort((a, b) => a - b);
  return values[Math.max(Math.ceil(q * values.length) - 1, 0)];
}

/** One row of M from rows of B and Π. */
export function blendRow(
  bRow: ArrayLike<number>,
  piRow: ArrayLike<number>,
  self: number,
  beta: number,
  cB: number,
  cPi: number,
): Float64Array {
  if (!(beta >= 0 && beta <= 1)) throw new Error('beta must be in [0, 1]');
  if (!(cB > 0 && cPi > 0)) throw new Error('scale constants must be positive');
  const out = new Float64Array(bRow.length);
  for (let i = 0; i < bRow.length; i++) {
    out[i] = i === self ? 0 : beta * (bRow[i] / cB) + (1 - beta) * (piRow[i] / cPi);
  }
  return out;
}

/** Keep the k entries of largest magnitude (ties by column). */
export function topKRow(row: Float64Array, k: number): Float64Array {
  if (k < 1) throw new Error('k must be at least 1');
  if (k >= row.length) return Float64Array.from(row);
  const order = Array.from(row.keys());
  order.sort((a, b) => {
    const x = Math.abs(row[a]);
    const y = Math.abs(row[b]);
    return x !== y ? (y > x ? 1 : -1) : a - b;
  });
  const out = new Float64Array(row.length);
  for (const i of order.slice(0, k)) out[i] = row[i];
  return out;
}

/** s = Σ_j x_j·M_j·, summed in history order. `rows[t]` is M's row for history entry t. */
export function score(weights: number[], rows: Float64Array[], n: number): Float64Array {
  const s = new Float64Array(n);
  rows.forEach((row, t) => {
    const x = weights[t];
    for (let i = 0; i < n; i++) s[i] = s[i] + x * row[i];
  });
  return s;
}
