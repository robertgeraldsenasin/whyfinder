"""The glass-box blend and scoring (FR-08).

    M = β·B/c_B + (1−β)·Π/c_Π,   diag(M) = 0,   s_u = x_u M

c_B and c_Π are global constants (the 99th percentile of the absolute non-zero entries), so the two
models are on comparable scales and the score stays exactly additive over the user's history.
"""

from __future__ import annotations

import numpy as np


def confidence(hours: np.ndarray, alpha: float, eps: float) -> np.ndarray:
    """x = 1 + α·log(1 + hours/ε) (same formula as `whyfinder.data.features`, ADR-0004)."""
    if alpha < 0 or eps <= 0:
        raise ValueError("need alpha ≥ 0 and eps > 0")
    return 1.0 + alpha * np.log1p(np.asarray(hours, dtype=np.float64) / eps)


def scale_constant(W: np.ndarray, q: float = 0.99) -> float:
    """Nearest-rank q-quantile of |W| over its non-zero off-diagonal entries (1.0 if none).

    Nearest rank (sorted ascending, index ⌈q·m⌉ − 1) is used so the browser engine can reproduce it
    exactly.
    """
    if not 0.0 < q <= 1.0:
        raise ValueError("q must be in (0, 1]")
    A = np.abs(np.array(W, dtype=np.float64))
    np.fill_diagonal(A, 0.0)
    values = np.sort(A[A > 0.0])
    if values.size == 0:
        return 1.0
    index = int(np.ceil(q * values.size)) - 1
    return float(values[max(index, 0)])


def blend(B: np.ndarray, Pi: np.ndarray, beta: float, c_B: float, c_Pi: float) -> np.ndarray:
    """M = β·B/c_B + (1−β)·Π/c_Π with a zero diagonal."""
    if not 0.0 <= beta <= 1.0:
        raise ValueError("beta must be in [0, 1]")
    if c_B <= 0 or c_Pi <= 0:
        raise ValueError("scale constants must be positive")
    if B.shape != Pi.shape:
        raise ValueError(f"shape mismatch: {B.shape} vs {Pi.shape}")
    M = beta * (B / c_B) + (1.0 - beta) * (Pi / c_Pi)
    np.fill_diagonal(M, 0.0)
    return np.asarray(M, dtype=np.float64)


def top_k_rows(W: np.ndarray, k: int) -> np.ndarray:
    """Keep the k entries of largest magnitude in each row (ties by column), zero the rest.

    The served model is the truncated matrix, so attributions stay exact for what is served.
    """
    if k < 1:
        raise ValueError("k must be at least 1")
    n_cols = W.shape[1]
    if k >= n_cols:
        return np.array(W, dtype=np.float64)
    out = np.zeros_like(W, dtype=np.float64)
    columns = np.arange(n_cols)
    for i, row in enumerate(W):
        order = np.lexsort((columns, -np.abs(row)))[:k]
        out[i, order] = row[order]
    return out


def score(history: list[tuple[int, float]], M: np.ndarray) -> np.ndarray:
    """s = Σ_j x_j M_j·, summed in history order (the order the browser engine uses too).

    `history` is a list of (game index, confidence weight).
    """
    s = np.zeros(M.shape[1], dtype=np.float64)
    for j, x in history:
        s = s + x * M[j]
    return s
