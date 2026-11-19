"""Baselines every model must beat (FR-04; docs/spec/04_ALGORITHMS.md §A1).

- **Popularity:** games ranked by their summed confidence in train. Everyone gets the same list.
- **Item-kNN:** sim(a, b) = G_ab / (‖a‖·‖b‖ + s) on the binary train columns, with shrinkage s
  damping pairs seen together only a few times; each game keeps its `top_k` most similar games.
  A user's score for game j is Σ_i x_i·S_ij, the same additive form as the glass-box blend.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from whyfinder.core.blend import top_k_rows


def popularity(X: sp.csr_matrix) -> np.ndarray:
    """Summed confidence per game (column sums of X), float64."""
    if X.ndim != 2:
        raise ValueError("X must be a matrix")
    return np.asarray(X.sum(axis=0), dtype=np.float64).ravel()


def gram(X: sp.csr_matrix) -> np.ndarray:
    """G = XᵀX on the binary pattern of X (co-occurrence counts), dense float64."""
    binary = X.copy().tocsr()
    binary.data = np.ones_like(binary.data, dtype=np.float64)
    return np.asarray((binary.T @ binary).toarray(), dtype=np.float64)


def item_knn(G: np.ndarray, *, shrinkage: float, top_k: int) -> np.ndarray:
    """Item-item similarity with shrinkage, top `top_k` per row, zero diagonal (n × n, float64).

    Pure: G is not modified. Raises ValueError for a non-square G, s < 0 or top_k < 1.
    """
    if G.ndim != 2 or G.shape[0] != G.shape[1]:
        raise ValueError(f"G must be square, got shape {G.shape}")
    if shrinkage < 0:
        raise ValueError("shrinkage must be non-negative")
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    norms = np.sqrt(np.clip(np.diag(G).astype(np.float64), 0.0, None))
    denominator = np.outer(norms, norms) + shrinkage
    with np.errstate(divide="ignore", invalid="ignore"):
        S = np.where(denominator > 0.0, np.asarray(G, dtype=np.float64) / denominator, 0.0)
    np.fill_diagonal(S, 0.0)
    return top_k_rows(S, top_k)
