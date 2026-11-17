"""EASE^R (Steck, WWW 2019): a closed-form item-item model with a zero diagonal (FR-05).

    P = (G + λI)⁻¹,   B_ij = −P_ij / P_jj (i ≠ j),   B_jj = 0

G = XᵀX is the Gram matrix of the binary training matrix. G + λI is symmetric positive definite, so
it is factored by Cholesky and inverted in float64. B is the item-item weight matrix: a user's score
for game j is Σ_i x_i B_ij, which is what makes the model's reasons exact.
"""

from __future__ import annotations

import numpy as np
import scipy.linalg as la


def ease(G: np.ndarray, lam: float) -> np.ndarray:
    """Item-item weights B (n × n, float64, zero diagonal) from a Gram matrix G.

    Pure: G is not modified. Raises ValueError for a non-square G or λ ≤ 0, and
    numpy.linalg.LinAlgError if G + λI is not positive definite.
    """
    if G.ndim != 2 or G.shape[0] != G.shape[1]:
        raise ValueError(f"G must be square, got shape {G.shape}")
    if lam <= 0:
        raise ValueError("lambda must be positive")
    A = np.array(G, dtype=np.float64)
    A[np.diag_indices_from(A)] += lam
    try:
        factor = la.cho_factor(A, lower=True, check_finite=True)
    except la.LinAlgError as error:
        raise np.linalg.LinAlgError("G + λI is not positive definite") from error
    P = la.cho_solve(factor, np.eye(A.shape[0]), check_finite=False)
    B = -P / np.diag(P)[None, :]
    np.fill_diagonal(B, 0.0)
    return np.asarray(B, dtype=np.float64)
