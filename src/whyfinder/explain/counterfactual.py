"""Counterfactual explanations (FR-11; ADR-0012): the smallest set of your games whose removal
drops a pick from the full pipeline's output.

Scores are linear in the history, so removing games needs no refitting: the pipeline (scoring,
filters, top 100, DPP) is simply re-run on the smaller history, which checks validity end to end.

- `greedy`: remove games in order of contribution until the pick drops, then repeatedly drop any
  game whose return still keeps the pick out. The result is valid and irreducible.
- `exact`: try every subset of size 1, 2, 3 of the largest contributors (smallest first, then by
  contribution rank). The first that works is a minimum among those.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import combinations

Pipeline = Callable[[list[tuple[int, float]]], list[int]]


@dataclass(frozen=True)
class Counterfactual:
    """The removal set and how the search got there (the live demo replays `trail`)."""

    pick: int
    removed: list[int]
    runs: int
    trail: list[tuple[str, list[int], bool]]  # (action, set tried, pick still shown?)


def _drops(
    pipeline: Pipeline, history: list[tuple[int, float]], removed: set[int], pick: int
) -> bool:
    rest = [(j, x) for j, x in history if j not in removed]
    return not rest or pick not in pipeline(rest)


def greedy(
    pipeline: Pipeline, history: list[tuple[int, float]], pick: int, order: list[int]
) -> Counterfactual:
    """Greedy removal in `order` (largest contribution first), then pruning to irreducible."""
    removed: list[int] = []
    trail: list[tuple[str, list[int], bool]] = []
    runs = 0
    for j in order:
        removed.append(j)
        runs += 1
        dropped = _drops(pipeline, history, set(removed), pick)
        trail.append(("remove", list(removed), not dropped))
        if dropped:
            break
    changed = True
    while changed and len(removed) > 1:
        changed = False
        for j in list(removed):
            trial = [g for g in removed if g != j]
            runs += 1
            dropped = _drops(pipeline, history, set(trial), pick)
            trail.append(("prune", trial, not dropped))
            if dropped:
                removed = trial
                changed = True
                break
    return Counterfactual(pick=pick, removed=removed, runs=runs, trail=trail)


def exact(
    pipeline: Pipeline,
    history: list[tuple[int, float]],
    pick: int,
    order: list[int],
    *,
    max_size: int = 3,
    pool: int = 20,
) -> Counterfactual | None:
    """Smallest removal set of size ≤ max_size among the `pool` largest contributors, or None."""
    top = order[:pool]
    runs = 0
    for size in range(1, max_size + 1):
        for subset in combinations(top, size):
            runs += 1
            if _drops(pipeline, history, set(subset), pick):
                return Counterfactual(pick=pick, removed=list(subset), runs=runs, trail=[])
    return None
