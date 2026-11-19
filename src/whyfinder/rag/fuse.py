"""Reciprocal rank fusion (04_ALGORITHMS.md §A10; Cormack, Clarke and Büttcher, SIGIR 2009)."""

from __future__ import annotations

from collections.abc import Sequence


def rrf(rankings: Sequence[Sequence[int]], k: int = 60) -> list[tuple[int, float]]:
    """score(d) = Σ_r 1 / (k + rank_r(d)), ranks from 1; best first, ties by document number.

    A document missing from a ranking gets nothing from it. Repeats within one ranking count once,
    at their best rank.
    """
    if k < 0:
        raise ValueError("k must be non-negative")
    scores: dict[int, float] = {}
    for ranking in rankings:
        seen: set[int] = set()
        for rank, doc in enumerate(ranking, start=1):
            if doc in seen:
                continue
            seen.add(doc)
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))
