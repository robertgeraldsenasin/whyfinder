"""The gate's statistics (ADR-0005; docs/spec/07_EVALUATION.md, "Statistics").

- **Paired bootstrap** of the mean difference head − base over users: resample users with
  replacement (the same resample for both models), 2,000 times by default, seed fixed. The 95%
  percentile interval is reported.
- **Non-inferiority** of head against base with margin δ: H0 says the true difference is ≤ −δ.
  Its bootstrap p-value is the share of resampled differences at or below −δ (with the usual +1
  correction). **Superiority** uses δ = 0.
- **Holm–Bonferroni** across the gated metrics of one run: sort the p-values, compare the j-th
  smallest with α / (m − j), stop at the first that fails.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Comparison:
    """head − base for one metric."""

    base: float
    head: float
    delta: float
    low: float
    high: float
    p_value: float
    margin: float
    n: int


def bootstrap_indices(n: int, resamples: int, seed: int) -> np.ndarray:
    """resamples × n user indices drawn with replacement (one generator, fixed seed)."""
    if n < 1 or resamples < 1:
        raise ValueError("need at least one user and one resample")
    return np.random.default_rng(seed).integers(0, n, size=(resamples, n))


def paired(
    base: np.ndarray,
    head: np.ndarray,
    *,
    margin: float,
    resamples: int = 2000,
    seed: int = 0,
    level: float = 0.95,
    indices: np.ndarray | None = None,
) -> Comparison:
    """Paired bootstrap of mean(head − base) and the non-inferiority p-value for margin δ ≥ 0."""
    base = np.asarray(base, dtype=np.float64)
    head = np.asarray(head, dtype=np.float64)
    if base.shape != head.shape or base.ndim != 1:
        raise ValueError("base and head must be 1-D arrays of the same length (one value per user)")
    if margin < 0:
        raise ValueError("margin must be non-negative")
    if not 0.0 < level < 1.0:
        raise ValueError("level must be in (0, 1)")
    diff = head - base
    idx = bootstrap_indices(diff.size, resamples, seed) if indices is None else indices
    means = diff[idx].mean(axis=1)
    tail = (1.0 - level) / 2.0
    low, high = np.quantile(means, [tail, 1.0 - tail])
    p = (int(np.sum(means <= -margin)) + 1) / (means.size + 1)
    return Comparison(
        base=float(base.mean()),
        head=float(head.mean()),
        delta=float(diff.mean()),
        low=float(low),
        high=float(high),
        p_value=float(p),
        margin=float(margin),
        n=int(diff.size),
    )


def holm(p_values: Sequence[float], alpha: float = 0.05) -> list[bool]:
    """Holm–Bonferroni step-down: which null hypotheses are rejected (True = passes the gate)."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    m = len(p_values)
    order = sorted(range(m), key=lambda j: (p_values[j], j))
    rejected = [False] * m
    for rank, j in enumerate(order):
        if p_values[j] <= alpha / (m - rank):
            rejected[j] = True
        else:
            break
    return rejected
