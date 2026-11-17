"""Exact attributions (FR-10; docs/spec/05_EXPLAINABILITY.md).

Because s_i = Σ_j x_j·M_ji, the contribution of history game j to pick i is exactly x_j·M_ji,
and the contributions summed in history order equal the score bit for bit. Each contribution also
splits into its EASE^R part x_j·β·B_ji/c_B and its PPR part x_j·(1−β)·Π_ji/c_Π.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Contribution:
    """One history game's share of one pick's score."""

    game: int
    total: float
    ease: float
    ppr: float


def attributions(
    history: list[tuple[int, float]],
    pick: int,
    M: np.ndarray,
    B: np.ndarray,
    Pi: np.ndarray,
    *,
    beta: float,
    c_B: float,
    c_Pi: float,
    game_ids: Sequence[int],
) -> list[Contribution]:
    """Contributions to `pick`, largest first (ties by game ID)."""
    out = [
        Contribution(
            game=j,
            total=x * float(M[j, pick]),
            ease=x * (beta * (float(B[j, pick]) / c_B)),
            ppr=x * ((1.0 - beta) * (float(Pi[j, pick]) / c_Pi)),
        )
        for j, x in history
    ]
    return sorted(out, key=lambda c: (-c.total, game_ids[c.game]))


def total_in_history_order(history: list[tuple[int, float]], pick: int, M: np.ndarray) -> float:
    """Σ_j x_j·M_ji in history order: equal to the pipeline's score for `pick`."""
    total = 0.0
    for j, x in history:
        total = total + x * float(M[j, pick])
    return total
