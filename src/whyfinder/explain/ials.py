"""Explanations for the iALS rival (FR-11; ADR-0012; docs/spec/05_EXPLAINABILITY.md, E1 and E2).

A folded-in user solves A x = b with

    A = YᵀY + λI + Σ_{j∈H} (c_j − 1) y_j y_jᵀ,    b = Σ_{j∈H} c_j y_j,    c_j = 1 + α w_j

(Hu, Koren and Volinsky, ICDM 2008). Two things follow.

- Attributions are exact: ŷ_i = y_iᵀ A⁻¹ b = Σ_j c_j y_iᵀ A⁻¹ y_j, a sum over the history.
- Removing game j takes a rank-one term out of A and c_j y_j out of b, so the Sherman–Morrison
  identity gives the new A⁻¹ in O(f²) instead of a fresh O(f³) solve:

      (A − s y yᵀ)⁻¹ = A⁻¹ + s A⁻¹y yᵀA⁻¹ / (1 − s yᵀA⁻¹y),   s = c_j − 1.

  The denominator is det(A')/det(A) > 0 because A' is still positive definite.

Unlike the blend, removing one game moves A⁻¹ and so every other game's contribution: a game's
attribution is not what removing it costs. That is why iALS counterfactuals need the re-scoring
search of `counterfactual.greedy`, and why the cheap update matters.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import scipy.linalg as la

from whyfinder.explain.counterfactual import Counterfactual, Pipeline, greedy


@dataclass(frozen=True)
class IalsUser:
    """A folded-in user: A⁻¹, b and each history game's confidence c_j."""

    inverse: np.ndarray
    b: np.ndarray
    confidence: dict[int, float]

    @property
    def factor(self) -> np.ndarray:
        return np.asarray(self.inverse @ self.b, dtype=np.float64)


def fold(history: list[tuple[int, float]], Y: np.ndarray, *, reg: float, alpha: float) -> IalsUser:
    """The state for a history of (game index, weight): the solve of `core.ials.fold_in`."""
    games = [j for j, _ in history]
    if len(set(games)) != len(games):
        raise ValueError("a game appears twice in the history")
    f = Y.shape[1]
    A = Y.T @ Y + reg * np.eye(f)
    b = np.zeros(f, dtype=np.float64)
    confidence: dict[int, float] = {}
    if history:
        cols = np.array(games, dtype=np.int64)
        c = 1.0 + alpha * np.array([w for _, w in history], dtype=np.float64)
        Yi = Y[cols]
        A = A + (Yi.T * (c - 1.0)) @ Yi
        b = Yi.T @ c
        confidence = {j: float(cj) for j, cj in zip(games, c, strict=True)}
    inverse = la.cho_solve(la.cho_factor(A), np.eye(f))
    return IalsUser(inverse=(inverse + inverse.T) / 2.0, b=b, confidence=confidence)


def without(user: IalsUser, j: int, Y: np.ndarray) -> IalsUser:
    """The user without game j, by a Sherman–Morrison downdate; inputs are left unchanged."""
    if j not in user.confidence:
        raise KeyError(f"game {j} is not in the history")
    c = user.confidence[j]
    y = Y[j]
    u = user.inverse @ y
    s = c - 1.0
    denominator = 1.0 - s * float(y @ u)
    if denominator <= 0.0:
        raise FloatingPointError("the downdated matrix is not positive definite")
    inverse = user.inverse + (s / denominator) * np.outer(u, u)
    confidence = {g: cg for g, cg in user.confidence.items() if g != j}
    return IalsUser(inverse=inverse, b=user.b - c * y, confidence=confidence)


def without_all(user: IalsUser, removed: Iterable[int], Y: np.ndarray) -> IalsUser:
    """Remove several games, one downdate each, in ascending index order."""
    for j in sorted(set(removed)):
        user = without(user, j, Y)
    return user


def attributions(
    user: IalsUser, Y: np.ndarray, pick: int, game_ids: np.ndarray
) -> list[tuple[int, float]]:
    """(history game, c_j y_pickᵀ A⁻¹ y_j), largest first, ties by game ID; sums to the score."""
    w = user.inverse @ Y[pick]
    parts = [(j, c * float(Y[j] @ w)) for j, c in user.confidence.items()]
    return sorted(parts, key=lambda p: (-p[1], int(game_ids[p[0]])))


def top(scores: np.ndarray, owned: set[int], game_ids: np.ndarray, k: int) -> list[int]:
    """The k best unowned games, ties by game ID."""
    order = np.lexsort((game_ids, -scores))
    return [int(i) for i in order if int(i) not in owned][:k]


def pipeline(user: IalsUser, Y: np.ndarray, game_ids: np.ndarray, k: int) -> Pipeline:
    """Top k for any part of the user's history, by downdating the full state (no re-solve)."""
    full = set(user.confidence)

    def run(rest: list[tuple[int, float]]) -> list[int]:
        kept = {j for j, _ in rest}
        if not kept <= full:
            raise KeyError("the pipeline only scores parts of the folded history")
        reduced = without_all(user, full - kept, Y)
        return top(Y @ reduced.factor, kept, game_ids, k)

    return run


def counterfactual(
    user: IalsUser, Y: np.ndarray, game_ids: np.ndarray, pick: int, k: int
) -> Counterfactual:
    """Greedy then pruned (ADR-0012): a valid, irreducible removal set for an iALS pick.

    The removal order is the attribution order. A pick outside the top k needs no removal.
    """
    history = [(j, c) for j, c in user.confidence.items()]
    run = pipeline(user, Y, game_ids, k)
    if pick not in run(history):
        return Counterfactual(pick=pick, removed=[], runs=1, trail=[])
    order = [j for j, _ in attributions(user, Y, pick, game_ids)]
    found = greedy(run, history, pick, order)
    return Counterfactual(pick=pick, removed=found.removed, runs=found.runs + 1, trail=found.trail)
