"""Randomized SVD against numpy (ADR-0010) and HNSW recall against exact search (FR-15)."""

from __future__ import annotations

import numpy as np
import pytest

from whyfinder.rag.hnsw import build, exact, levels
from whyfinder.rag.lsa import fit, randomized_svd


def unit(rows: int, dim: int, seed: int) -> np.ndarray:
    X = np.random.default_rng(seed).standard_normal((rows, dim))
    return X / np.linalg.norm(X, axis=1, keepdims=True)


def test_randomized_svd_recovers_a_low_rank_matrix() -> None:
    rng = np.random.default_rng(0)
    A = rng.standard_normal((80, 6)) @ rng.standard_normal((6, 50))
    U, s, Vt = randomized_svd(A, 6, seed=3)
    assert np.allclose(s, np.linalg.svd(A, compute_uv=False)[:6], atol=1e-9)
    assert np.allclose(U @ np.diag(s) @ Vt, A, atol=1e-9)
    assert np.allclose(Vt @ Vt.T, np.eye(6), atol=1e-10)
    again = randomized_svd(A, 6, seed=3)
    assert all(np.array_equal(x, y) for x, y in zip((U, s, Vt), again, strict=True))
    with pytest.raises(ValueError, match="need 1 <= k"):
        randomized_svd(A, 0)


def test_randomized_svd_is_close_on_a_full_rank_matrix() -> None:
    A = np.random.default_rng(1).standard_normal((120, 60))
    _, s, _ = randomized_svd(A, 10, power=4, seed=0)
    exact_s = np.linalg.svd(A, compute_uv=False)[:10]
    assert np.max(np.abs(s - exact_s) / exact_s) < 0.05


def test_lsa_embeds_similar_texts_near_each_other() -> None:
    docs = [
        ["fast", "combat", "tight"],
        ["combat", "fast", "smooth"],
        ["story", "characters", "writing"],
        ["writing", "story", "plot"],
        ["fast", "combat"],
        ["story", "plot"],
    ]
    model = fit(docs, dim=2, min_df=2, seed=0)
    V = model.embed(docs)
    assert np.allclose(np.linalg.norm(V, axis=1), 1.0)
    q = model.embed([["combat"]])[0]
    sims = V @ q
    assert set(np.argsort(-sims)[:3]) == {0, 1, 4}
    assert np.array_equal(model.embed([["unknown"]]), np.zeros((1, model.dim)))
    with pytest.raises(ValueError, match="min_df"):
        fit([["a"], ["b"]], min_df=2)


@pytest.mark.parametrize(("dim", "seed"), [(16, 0), (32, 1)])
def test_hnsw_recall_at_10_is_at_least_095(dim: int, seed: int) -> None:
    X = unit(1500, dim, seed)
    Q = unit(100, dim, seed + 100)
    index = build(X, m=16, ef_construction=100, seed=seed)
    recall = np.mean(
        [
            len({i for i, _ in index.search(q, 10, ef=64)} & {i for i, _ in exact(X, q, 10)}) / 10
            for q in Q
        ]
    )
    assert recall >= 0.95


def test_hnsw_is_reproducible_and_respects_its_caps() -> None:
    X = unit(400, 8, 2)
    a, b = build(X, m=4, ef_construction=20, seed=7), build(X, m=4, ef_construction=20, seed=7)
    assert a.links == b.links
    assert (a.entry, a.top) == (b.entry, b.top)
    for node in a.links:
        assert len(node[0]) <= 8
        assert all(len(layer) <= 4 for layer in node[1:])
    assert levels(5, 4, seed=7) == levels(5, 4, seed=7)


def test_hnsw_search_edges() -> None:
    X = unit(30, 4, 3)
    index = build(X, m=4, ef_construction=10, seed=0)
    hits = index.search(X[5], 3)
    assert hits[0][0] == 5
    assert hits[0][1] == pytest.approx(1.0)
    assert [s for _, s in hits] == sorted((s for _, s in hits), reverse=True)
    assert len(index.search(X[0], 100, ef=10)) == 30
    assert index.search(X[0], 0) == []
    assert build(np.zeros((0, 4))).search(X[0], 3) == []
    with pytest.raises(ValueError, match="2-D"):
        build(X[0])
    with pytest.raises(ValueError, match="m >= 2"):
        build(X, m=1)


def test_hnsw_does_not_change_its_input() -> None:
    X = unit(50, 4, 4)
    before = X.copy()
    index = build(X, m=4, ef_construction=10)
    index.vectors[0] = 0.0
    assert np.array_equal(X, before)
