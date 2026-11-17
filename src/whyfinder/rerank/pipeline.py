"""The full recommendation pipeline (docs/spec/04_ALGORITHMS.md, "Pipeline at a glance"):

    history → s = x·M → drop owned, apply filters → top 100 → DPP → top 10

Counterfactual search re-runs exactly this function, so its guarantees hold end to end.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from whyfinder.core.blend import score
from whyfinder.rerank.dpp import DppStep, SparseVector, greedy_map


class EmptyHistoryError(ValueError):
    """Recommendations need at least one game in the history."""


@dataclass(frozen=True)
class Recommendation:
    """Everything one run produced, kept for explanations and the live demo."""

    scores: np.ndarray
    candidates: list[int]
    relevance_top: list[int]
    picks: list[int]
    variety: list[bool]
    steps: list[DppStep]


def rank_candidates(
    scores: np.ndarray,
    game_ids: Sequence[int],
    excluded: set[int],
    allowed: Sequence[bool] | None,
    n: int,
) -> list[int]:
    """Indices by score descending, ties by game ID; owned and filtered-out games removed."""
    pool = [i for i in range(len(scores)) if i not in excluded and (allowed is None or allowed[i])]
    pool.sort(key=lambda i: (-scores[i], game_ids[i]))
    return pool[:n]


def recommend(
    history: list[tuple[int, float]],
    M: np.ndarray,
    *,
    vectors: Sequence[SparseVector],
    game_ids: Sequence[int],
    k: int = 10,
    n_candidates: int = 100,
    theta: float = 2.0,
    allowed: Sequence[bool] | None = None,
) -> Recommendation:
    """Run the pipeline for one history of (game index, confidence) pairs."""
    if not history:
        raise EmptyHistoryError("history is empty")
    s = score(history, M)
    owned = {j for j, _ in history}
    candidates = rank_candidates(s, game_ids, owned, allowed, n_candidates)
    picks, steps = greedy_map(
        candidates,
        [float(s[i]) for i in candidates],
        vectors,
        game_ids,
        k=k,
        theta=theta,
    )
    relevance_top = candidates[:k]
    top = set(relevance_top)
    return Recommendation(
        scores=s,
        candidates=candidates,
        relevance_top=relevance_top,
        picks=picks,
        variety=[p not in top for p in picks],
        steps=steps,
    )
