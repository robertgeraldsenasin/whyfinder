from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from whyfinder.core.blend import blend, confidence, scale_constant, score, top_k_rows
from whyfinder.core.ease import ease


def gram_fixture(n_items: int, n_users: int = 2000, seed: int = 11) -> np.ndarray:
    rng = np.random.default_rng(seed)
    popularity = rng.pareto(1.5, n_items) + 0.05
    X = rng.random((n_users, n_items)) < np.clip(popularity / popularity.sum() * 25, 0, 0.9)
    Xf = X.astype(np.float64)
    return Xf.T @ Xf


def test_ease_matches_the_dense_inverse_on_300_items() -> None:
    G = gram_fixture(300)
    lam = 50.0
    B = ease(G, lam)
    P = np.linalg.inv(G + lam * np.eye(300))
    reference = -P / np.diag(P)[None, :]
    np.fill_diagonal(reference, 0.0)
    assert np.max(np.abs(B - reference)) < 1e-8
    assert np.all(np.diag(B) == 0.0)


def test_ease_is_the_constrained_least_squares_solution() -> None:
    # Steck's closed form: (G + λI)·B = G − (G + λI)·diag(μ) with B_jj = 0; check column-wise.
    G = gram_fixture(40, n_users=300)
    lam = 10.0
    B = ease(G, lam)
    A = G + lam * np.eye(40)
    residual = A @ B - G
    off = residual - np.diag(np.diag(residual))
    assert np.max(np.abs(off)) < 1e-8


def test_ease_does_not_mutate_and_rejects_bad_input() -> None:
    G = gram_fixture(10, n_users=50)
    before = G.copy()
    ease(G, 5.0)
    assert np.array_equal(G, before)
    with pytest.raises(ValueError, match="square"):
        ease(np.zeros((2, 3)), 1.0)
    with pytest.raises(ValueError, match="positive"):
        ease(G, 0.0)
    with pytest.raises(np.linalg.LinAlgError, match="positive definite"):
        ease(-np.eye(3) * 10, 1.0)


def test_scale_constant_is_nearest_rank() -> None:
    W = np.array([[9.0, 1.0, -2.0], [3.0, 0.0, 4.0], [0.0, -5.0, 7.0]])
    # off-diagonal |values| > 0: 1, 2, 3, 4, 5 → q=0.5 → ⌈2.5⌉−1 = index 2 → 3
    assert scale_constant(W, 0.5) == 3.0
    assert scale_constant(W, 1.0) == 5.0
    assert scale_constant(np.eye(3)) == 1.0
    with pytest.raises(ValueError, match="q must"):
        scale_constant(W, 0.0)


def test_blend_formula_and_errors() -> None:
    B = np.array([[0.0, 2.0], [4.0, 0.0]])
    Pi = np.array([[0.5, 0.1], [0.3, 0.5]])
    M = blend(B, Pi, 0.25, 2.0, 0.1)
    assert M[0, 1] == pytest.approx(0.25 * 1.0 + 0.75 * 1.0)
    assert M[1, 0] == pytest.approx(0.25 * 2.0 + 0.75 * 3.0)
    assert np.all(np.diag(M) == 0.0)
    with pytest.raises(ValueError, match="beta"):
        blend(B, Pi, 1.5, 1.0, 1.0)
    with pytest.raises(ValueError, match="positive"):
        blend(B, Pi, 0.5, 0.0, 1.0)
    with pytest.raises(ValueError, match="shape"):
        blend(B, np.zeros((3, 3)), 0.5, 1.0, 1.0)


def test_top_k_rows_keeps_largest_magnitudes_ties_by_column() -> None:
    W = np.array([[1.0, -3.0, 3.0, 0.5], [2.0, 2.0, 2.0, 2.0]])
    out = top_k_rows(W, 2)
    assert out.tolist() == [[0.0, -3.0, 3.0, 0.0], [2.0, 2.0, 0.0, 0.0]]
    assert np.array_equal(top_k_rows(W, 9), W)
    with pytest.raises(ValueError, match="k must"):
        top_k_rows(W, 0)


def test_confidence_matches_the_data_layer_formula() -> None:
    from whyfinder.data.features import confidence as data_confidence

    hours = np.array([0.0, 0.5, 12.0, 300.0])
    assert np.array_equal(confidence(hours, 1.0, 1.0), data_confidence(hours, 1.0, 1.0))
    with pytest.raises(ValueError, match="alpha"):
        confidence(hours, -1.0, 1.0)


@settings(max_examples=60, deadline=None)
@given(
    st.integers(2, 12),
    st.lists(st.floats(0.5, 20.0), min_size=1, max_size=6),
    st.integers(0, 10_000),
)
def test_score_is_exactly_additive(n: int, weights: list[float], seed: int) -> None:
    rng = np.random.default_rng(seed)
    M = rng.normal(size=(n, n))
    history = [(int(j), w) for j, w in zip(rng.permutation(n), weights, strict=False)]
    s = score(history, M)
    for i in range(n):
        total = 0.0
        for j, x in history:
            total = total + x * M[j, i]
        assert s[i] == total  # bit-for-bit, not just close
