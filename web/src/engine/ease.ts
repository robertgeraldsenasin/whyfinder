/**
 * EASE^R (Steck, WWW 2019), hand-written: P = (G + λI)⁻¹ by Cholesky, B_ij = −P_ij / P_jj, B_jj = 0.
 * Twin of src/whyfinder/core/ease.py; golden-matched in ease.test.ts.
 */

export interface EaseProgress {
  phase: 'cholesky' | 'invert' | 'weights';
  done: number;
  total: number;
}

/** Unpack the slice's row-major upper triangle into a full symmetric n × n matrix. */
export function unpackUpper(packed: ArrayLike<number>, n: number): Float64Array {
  if (packed.length !== (n * (n + 1)) / 2) {
    throw new Error(`packed length ${packed.length} does not fit n=${n}`);
  }
  const G = new Float64Array(n * n);
  let k = 0;
  for (let i = 0; i < n; i++) {
    for (let j = i; j < n; j++) {
      const v = packed[k++];
      G[i * n + j] = v;
      G[j * n + i] = v;
    }
  }
  return G;
}

/** Lower Cholesky factor L of a symmetric positive-definite A (row-major, n × n). */
export function cholesky(
  A: Float64Array,
  n: number,
  onProgress?: (p: EaseProgress) => void,
): Float64Array {
  const L = new Float64Array(n * n);
  for (let j = 0; j < n; j++) {
    let s = A[j * n + j];
    const rowJ = j * n;
    for (let k = 0; k < j; k++) s -= L[rowJ + k] * L[rowJ + k];
    if (!(s > 0)) throw new Error('G + λI is not positive definite');
    const d = Math.sqrt(s);
    L[rowJ + j] = d;
    for (let i = j + 1; i < n; i++) {
      const rowI = i * n;
      let t = A[rowI + j];
      for (let k = 0; k < j; k++) t -= L[rowI + k] * L[rowJ + k];
      L[rowI + j] = t / d;
    }
    if (onProgress && (j % 25 === 0 || j === n - 1)) onProgress({ phase: 'cholesky', done: j + 1, total: n });
  }
  return L;
}

/** A⁻¹ = L⁻ᵀ L⁻¹ from the Cholesky factor. */
export function inverseFromCholesky(
  L: Float64Array,
  n: number,
  onProgress?: (p: EaseProgress) => void,
): Float64Array {
  // Linv: inverse of lower-triangular L, column by column (forward substitution).
  const Linv = new Float64Array(n * n);
  for (let j = 0; j < n; j++) {
    Linv[j * n + j] = 1 / L[j * n + j];
    for (let i = j + 1; i < n; i++) {
      let s = 0;
      for (let k = j; k < i; k++) s -= L[i * n + k] * Linv[k * n + j];
      Linv[i * n + j] = s / L[i * n + i];
    }
    if (onProgress && (j % 25 === 0 || j === n - 1)) onProgress({ phase: 'invert', done: j + 1, total: n });
  }
  // P = Linvᵀ Linv: P_ij = Σ_{k ≥ max(i,j)} Linv_ki Linv_kj.
  const P = new Float64Array(n * n);
  for (let i = 0; i < n; i++) {
    for (let j = i; j < n; j++) {
      let s = 0;
      for (let k = j; k < n; k++) s += Linv[k * n + i] * Linv[k * n + j];
      P[i * n + j] = s;
      P[j * n + i] = s;
    }
  }
  return P;
}

/** B from the Gram matrix G (row-major n × n). Pure: G is not modified. */
export function ease(
  G: Float64Array,
  n: number,
  lambda: number,
  onProgress?: (p: EaseProgress) => void,
): Float64Array {
  if (G.length !== n * n) throw new Error(`G must be ${n} × ${n}`);
  if (!(lambda > 0)) throw new Error('lambda must be positive');
  const A = Float64Array.from(G);
  for (let i = 0; i < n; i++) A[i * n + i] += lambda;
  const L = cholesky(A, n, onProgress);
  const P = inverseFromCholesky(L, n, onProgress);
  const B = new Float64Array(n * n);
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      B[i * n + j] = i === j ? 0 : -P[i * n + j] / P[j * n + j];
    }
  }
  onProgress?.({ phase: 'weights', done: n, total: n });
  return B;
}
