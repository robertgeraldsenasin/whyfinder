"""Per-user ranking and beyond-accuracy metrics (docs/spec/07_EVALUATION.md, "Metrics").

Every function returns one value per user (NumPy arrays aligned with the input lists), because the
quality gate compares two models user by user. Relevance is binary: a game the user played in the
held-out period. Lists are best first.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from whyfinder.rerank.dpp import SparseVector, similarity

_LOG2 = 1.0 / np.log2(np.arange(2, 202, dtype=np.float64))  # 1/log2(rank + 1) for ranks 1..200


def _check(k: int) -> None:
    if not 1 <= k <= len(_LOG2):
        raise ValueError(f"k must be in [1, {len(_LOG2)}]")


def ndcg_at(ranked: Sequence[Sequence[int]], relevant: Sequence[set[int]], k: int) -> np.ndarray:
    """NDCG@k: DCG of the first k items over the best possible DCG (min(|relevant|, k) hits)."""
    _check(k)
    out = np.zeros(len(ranked), dtype=np.float64)
    for u, (items, rel) in enumerate(zip(ranked, relevant, strict=True)):
        if not rel:
            continue
        dcg = sum(_LOG2[r] for r, i in enumerate(items[:k]) if i in rel)
        ideal = float(np.sum(_LOG2[: min(len(rel), k)]))
        out[u] = dcg / ideal
    return out


def recall_at(ranked: Sequence[Sequence[int]], relevant: Sequence[set[int]], k: int) -> np.ndarray:
    """Recall@k: share of the relevant games found in the first k (0 for a user with none)."""
    _check(k)
    out = np.zeros(len(ranked), dtype=np.float64)
    for u, (items, rel) in enumerate(zip(ranked, relevant, strict=True)):
        if rel:
            out[u] = sum(1 for i in items[:k] if i in rel) / len(rel)
    return out


def mrr(ranked: Sequence[Sequence[int]], relevant: Sequence[set[int]]) -> np.ndarray:
    """Reciprocal rank of the first relevant game in the list (0 when none appears)."""
    out = np.zeros(len(ranked), dtype=np.float64)
    for u, (items, rel) in enumerate(zip(ranked, relevant, strict=True)):
        for r, i in enumerate(items):
            if i in rel:
                out[u] = 1.0 / (r + 1)
                break
    return out


def coverage(ranked: Sequence[Sequence[int]], n_items: int, k: int) -> float:
    """Catalogue coverage@k: share of the n games recommended to at least one user."""
    _check(k)
    if n_items < 1:
        raise ValueError("n_items must be positive")
    seen = {i for items in ranked for i in items[:k]}
    return len(seen) / n_items


def ild(ranked: Sequence[Sequence[int]], vectors: Sequence[SparseVector], k: int) -> np.ndarray:
    """Intra-list diversity@k: 1 − mean pairwise tag cosine of the first k games (0 below 2)."""
    _check(k)
    out = np.zeros(len(ranked), dtype=np.float64)
    for u, items in enumerate(ranked):
        top = list(items[:k])
        if len(top) < 2:
            continue
        sims = [similarity(vectors[a], vectors[b]) for x, a in enumerate(top) for b in top[x + 1 :]]
        out[u] = 1.0 - float(np.mean(sims))
    return out


def arp(ranked: Sequence[Sequence[int]], popularity: np.ndarray, k: int) -> np.ndarray:
    """Average recommendation popularity@k: mean train popularity of the first k games."""
    _check(k)
    out = np.zeros(len(ranked), dtype=np.float64)
    for u, items in enumerate(ranked):
        top = list(items[:k])
        if top:
            out[u] = float(np.mean(popularity[top]))
    return out
