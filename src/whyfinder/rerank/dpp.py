"""DPP re-ranking by greedy MAP inference with incremental Cholesky (FR-12).

Chen, Zhang & Zhou, NeurIPS 2018. Kernel L = Diag(q)·S·Diag(q) with q_i = exp(θ·ŝ_i) (ŝ: the blend
score rescaled to [0, 1] within the candidates) and S_ij = f_i·f_j for L2-normalised TF-IDF
tag-and-genre vectors f (S_ii = 1, also for a game with no tags). Each step picks the candidate
with the largest d_i² = det(L_{Y∪i}) / det(L_Y), ties by game ID, then updates every other
candidate's Cholesky row in O(|Y|).

Every sum runs over features or steps in ascending order, so the browser engine reproduces the
picks exactly.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

SparseVector = list[tuple[int, float]]  # (feature index, value), feature index ascending
MIN_GAIN = 1e-12


def tfidf_vectors(features: Sequence[Sequence[str]]) -> list[SparseVector]:
    """Binary TF-IDF over sorted vocabulary, idf(t) = ln(1 + n / df(t)), L2-normalised."""
    df: dict[str, int] = {}
    for items in features:
        for f in dict.fromkeys(items):
            df[f] = df.get(f, 0) + 1
    vocabulary = {f: k for k, f in enumerate(sorted(df))}
    n = len(features)
    idf = {f: math.log(1.0 + n / count) for f, count in df.items()}
    vectors: list[SparseVector] = []
    for items in features:
        entries = sorted((vocabulary[f], idf[f]) for f in dict.fromkeys(items))
        total = 0.0
        for _, v in entries:
            total += v * v
        norm = math.sqrt(total)
        vectors.append([(k, v / norm) for k, v in entries] if norm > 0.0 else [])
    return vectors


def similarity(a: SparseVector, b: SparseVector) -> float:
    """f_a·f_b, summed over shared features in ascending order."""
    i = j = 0
    total = 0.0
    while i < len(a) and j < len(b):
        if a[i][0] == b[j][0]:
            total += a[i][1] * b[j][1]
            i += 1
            j += 1
        elif a[i][0] < b[j][0]:
            i += 1
        else:
            j += 1
    return total


@dataclass(frozen=True)
class DppStep:
    """One greedy step, for the live demo: who was picked and every remaining d²."""

    picked: int
    gain: float
    gains: dict[int, float]


def rescale(scores: Sequence[float]) -> list[float]:
    """Min-max to [0, 1]; all ones when the scores are equal."""
    lo, hi = min(scores), max(scores)
    if hi <= lo:
        return [1.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


def greedy_map(
    candidates: Sequence[int],
    scores: Sequence[float],
    vectors: Sequence[SparseVector],
    game_ids: Sequence[int],
    *,
    k: int,
    theta: float,
) -> tuple[list[int], list[DppStep]]:
    """Pick up to k of `candidates` (catalogue indices, in relevance order).

    If every remaining gain drops below 1e-12 (the rest are linear combinations of the picks), the
    list is completed in relevance order and those picks are not marked as DPP steps.
    """
    if k < 1:
        raise ValueError("k must be at least 1")
    if len(candidates) != len(scores):
        raise ValueError("candidates and scores differ in length")
    quality = [math.exp(theta * s) for s in rescale(scores)] if candidates else []
    q = dict(zip(candidates, quality, strict=True))
    d2 = {i: q[i] * 1.0 * q[i] for i in candidates}  # S_ii = 1
    rows: dict[int, list[float]] = {i: [] for i in candidates}
    remaining = list(candidates)
    picks: list[int] = []
    steps: list[DppStep] = []
    while remaining and len(picks) < k:
        j = remaining[0]
        for i in remaining[1:]:
            if d2[i] > d2[j] or (d2[i] == d2[j] and game_ids[i] < game_ids[j]):
                j = i
        if d2[j] < MIN_GAIN:
            break
        steps.append(DppStep(picked=j, gain=d2[j], gains={i: d2[i] for i in remaining}))
        picks.append(j)
        remaining.remove(j)
        dj = math.sqrt(d2[j])
        cj = rows[j]
        for i in remaining:
            ci = rows[i]
            dot = 0.0
            for t in range(len(cj)):
                dot += cj[t] * ci[t]
            L_ji = q[j] * similarity(vectors[j], vectors[i]) * q[i]
            e = (L_ji - dot) / dj
            ci.append(e)
            d2[i] = d2[i] - e * e
    for i in candidates:
        if len(picks) >= k:
            break
        if i not in picks:
            picks.append(i)
    return picks, steps
