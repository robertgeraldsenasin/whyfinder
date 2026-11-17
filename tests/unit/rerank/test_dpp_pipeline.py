from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from whyfinder.rerank.dpp import greedy_map, rescale, similarity, tfidf_vectors
from whyfinder.rerank.pipeline import EmptyHistoryError, rank_candidates, recommend

TAGS = ["rogue", "action", "puzzle", "coop", "story", "rpg", "horror", "sim"]


def features(n: int, seed: int) -> list[list[str]]:
    rng = np.random.default_rng(seed)
    return [list(rng.choice(TAGS, size=rng.integers(0, 4), replace=False)) for _ in range(n)]


def kernel(cands: list[int], scores: list[float], vectors: list, theta: float) -> np.ndarray:
    q = [math.exp(theta * s) for s in rescale(scores)]
    n = len(cands)
    L = np.zeros((n, n))
    for a, b in itertools.product(range(n), range(n)):
        sim = 1.0 if a == b else similarity(vectors[cands[a]], vectors[cands[b]])
        L[a, b] = q[a] * sim * q[b]
    return L


def test_tfidf_vectors_are_normalised_and_sorted() -> None:
    vectors = tfidf_vectors([["b", "a"], ["a"], []])
    assert vectors[2] == []
    assert [k for k, _ in vectors[0]] == [0, 1]
    assert sum(v * v for _, v in vectors[0]) == pytest.approx(1.0)
    assert similarity(vectors[0], vectors[1]) == pytest.approx(vectors[0][0][1])
    assert similarity(vectors[1], vectors[2]) == 0.0


@pytest.mark.parametrize("seed", range(8))
def test_greedy_equals_naive_determinant_greedy_on_12_candidates(seed: int) -> None:
    rng = np.random.default_rng(seed)
    feats = features(12, seed)
    vectors = tfidf_vectors(feats)
    cands = list(range(12))
    scores = sorted(rng.random(12).tolist(), reverse=True)
    ids = list(range(100, 112))
    picks, steps = greedy_map(cands, scores, vectors, ids, k=5, theta=2.0)
    L = kernel(cands, scores, vectors, 2.0)

    chosen: list[int] = []
    for step in steps:

        def gain(i: int, chosen: list[int] = chosen) -> float:
            idx = [*chosen, i]
            base = np.linalg.det(L[np.ix_(chosen, chosen)]) if chosen else 1.0
            return float(np.linalg.det(L[np.ix_(idx, idx)]) / base)

        rest = [i for i in cands if i not in chosen]
        best = max(gain(i) for i in rest)
        assert step.gain == pytest.approx(best, rel=1e-9)
        assert gain(step.picked) == pytest.approx(best, rel=1e-9)
        chosen.append(step.picked)
    # first pick is the brute-force argmax of log det over singletons: the most relevant game
    assert picks[0] == int(np.argmax(np.diag(L)))
    assert len(set(picks)) == len(picks) == 5


def test_brute_force_optimum_is_recorded_not_asserted() -> None:
    feats = features(12, 42)
    vectors = tfidf_vectors(feats)
    scores = [1 - i / 12 for i in range(12)]
    picks, _ = greedy_map(list(range(12)), scores, vectors, list(range(12)), k=3, theta=2.0)
    L = kernel(list(range(12)), scores, vectors, 2.0)
    best = max(np.linalg.slogdet(L[np.ix_(s, s)])[1] for s in itertools.combinations(range(12), 3))
    greedy_value = np.linalg.slogdet(L[np.ix_(picks, picks)])[1]
    assert greedy_value <= best + 1e-9


def test_duplicates_fall_back_to_relevance_order() -> None:
    vectors = tfidf_vectors([["a"]] * 4)  # identical games: after one pick every gain is ~0
    vectors = [v for v in vectors]
    picks, steps = greedy_map([0, 1, 2, 3], [4, 3, 2, 1], vectors, [0, 1, 2, 3], k=3, theta=1.0)
    assert picks == [0, 1, 2]
    assert len(steps) == 1


def test_ties_break_by_game_id_and_errors() -> None:
    vectors = tfidf_vectors([["a"], ["b"]])
    picks, _ = greedy_map([0, 1], [1.0, 1.0], vectors, [9, 3], k=1, theta=1.0)
    assert picks == [1]
    with pytest.raises(ValueError, match="k must"):
        greedy_map([0], [1.0], vectors, [0], k=0, theta=1.0)
    with pytest.raises(ValueError, match="length"):
        greedy_map([0, 1], [1.0], vectors, [0, 1], k=1, theta=1.0)
    assert rescale([2.0, 2.0]) == [1.0, 1.0]


def test_recommend_excludes_owned_applies_filters_and_flags_variety() -> None:
    rng = np.random.default_rng(5)
    n = 40
    M = rng.random((n, n))
    np.fill_diagonal(M, 0.0)
    feats = [["same"] if i % 2 == 0 else [f"t{i}"] for i in range(n)]
    vectors = tfidf_vectors(feats)
    ids = list(range(1000, 1000 + n))
    history = [(0, 1.0), (5, 2.0)]
    allowed = [i != 7 for i in range(n)]
    rec = recommend(
        history, M, vectors=vectors, game_ids=ids, k=10, n_candidates=30, theta=0.5, allowed=allowed
    )
    assert 0 not in rec.picks
    assert 5 not in rec.picks
    assert 7 not in rec.candidates
    assert len(rec.picks) == 10
    assert rec.relevance_top == rec.candidates[:10]
    assert rec.variety == [p not in rec.relevance_top for p in rec.picks]
    assert any(rec.variety)  # many near-duplicates ("same") → variety kicks in
    with pytest.raises(EmptyHistoryError):
        recommend([], M, vectors=vectors, game_ids=ids)


def test_rank_candidates_ties_by_game_id() -> None:
    scores = np.array([1.0, 2.0, 2.0, 0.5])
    assert rank_candidates(scores, [10, 30, 20, 40], {3}, None, 9) == [2, 1, 0]
