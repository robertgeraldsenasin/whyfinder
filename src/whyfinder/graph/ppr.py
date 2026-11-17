"""Personalized PageRank by forward push (FR-07; Andersen, Chung & Lang, FOCS 2006).

PPR from seed g solves π = α·e_g + (1−α)·π·P with P = D⁻¹W. Push keeps an estimate p and a residual
r (r = e_g at the start). Here pushes run in synchronous rounds: in each round every node v with
r(v) > ε·d(v) moves α·r(v) into p(v) and spreads (1−α)·r(v) to its neighbours in proportion to edge
weight. Rounds end when no node is above its threshold, which gives the classic guarantee
|π(v) − p(v)| ≤ ε·d(v). A node with no edges keeps its whole residual.

The order of every floating-point operation is fixed (ascending node order, contributions summed
into a fresh accumulator, then added to the kept residual), so the browser engine reproduces p
exactly; rounds also make a natural animation ("the wave reaches tags, then other games").
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from whyfinder.graph.build import Graph


@dataclass(frozen=True)
class PushResult:
    """Estimate p over all nodes, plus the work done."""

    p: np.ndarray
    rounds: int
    pushes: int
    residual_mass: float


def push(graph: Graph, seed: int, *, alpha: float, eps: float) -> PushResult:
    """Forward push from `seed` (synchronous rounds; see the module docstring)."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    if eps <= 0.0:
        raise ValueError("eps must be positive")
    n = graph.n_nodes
    if not 0 <= seed < n:
        raise ValueError(f"seed {seed} is not a node")
    degree = graph.degree
    threshold = eps * degree
    keep = np.where(degree > 0.0, alpha, 1.0)
    counts = np.diff(graph.indptr)
    p = np.zeros(n, dtype=np.float64)
    r = np.zeros(n, dtype=np.float64)
    r[seed] = 1.0
    rounds = pushes = 0
    while True:
        active = np.flatnonzero(r > threshold)
        if active.size == 0:
            break
        rounds += 1
        pushes += int(active.size)
        ra = r[active]
        p[active] = p[active] + keep[active] * ra
        spreading = active[degree[active] > 0.0]
        f = (1.0 - alpha) * r[spreading] / degree[spreading]
        starts, sizes = graph.indptr[spreading], counts[spreading]
        positions = np.repeat(starts - np.cumsum(sizes) + sizes, sizes) + np.arange(sizes.sum())
        targets = graph.indices[positions]
        contributions = np.repeat(f, sizes) * graph.weights[positions]
        acc = np.bincount(targets, weights=contributions, minlength=n)
        kept = r.copy()
        kept[active] = 0.0
        r = kept + acc
    return PushResult(p=p, rounds=rounds, pushes=pushes, residual_mass=float(r.sum()))


def pi_row(graph: Graph, seed: int, *, alpha: float, eps: float, top_m: int) -> np.ndarray:
    """Row `seed` of Π: the top `top_m` game entries of p (seed excluded, ties by index)."""
    p = push(graph, seed, alpha=alpha, eps=eps).p[: graph.n_games].copy()
    p[seed] = 0.0
    return keep_top(p, top_m)


def keep_top(row: np.ndarray, m: int) -> np.ndarray:
    """Zero all but the `m` largest positive entries (ties by index)."""
    order = np.lexsort((np.arange(row.size), -row))[:m]
    out = np.zeros_like(row)
    chosen = order[row[order] > 0.0]
    out[chosen] = row[chosen]
    return out


def pi_rows(graph: Graph, *, alpha: float, eps: float, top_m: int) -> tuple[np.ndarray, np.ndarray]:
    """Π for every game plus each row's truncation loss: the share of the row's game mass (seed
    excluded) that falls outside the kept top `top_m` entries."""
    rows, losses = [], []
    for g in range(graph.n_games):
        p = push(graph, g, alpha=alpha, eps=eps).p[: graph.n_games].copy()
        p[g] = 0.0
        row = keep_top(p, top_m)
        total = float(p[p > 0.0].sum())
        dropped = float(p[(p > 0.0) & (row == 0.0)].sum())
        rows.append(row)
        losses.append(dropped / total if total > 0.0 else 0.0)
    return np.vstack(rows), np.array(losses)


def pi_matrix(graph: Graph, *, alpha: float, eps: float, top_m: int) -> np.ndarray:
    """Π for every game (n_games × n_games), one push per seed."""
    return pi_rows(graph, alpha=alpha, eps=eps, top_m=top_m)[0]
