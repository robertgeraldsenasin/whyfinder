from __future__ import annotations

import itertools

import numpy as np
import pytest
import scipy.sparse as sp

from whyfinder.core.ials import fold_in, ials, loss, solve_rows_cg, solve_rows_cholesky


def fixture(m: int = 60, n: int = 40, seed: int = 5) -> sp.csr_matrix:
    rng = np.random.default_rng(seed)
    X = sp.random(m, n, density=0.15, random_state=rng, format="csr")
    X.data = 1.0 + np.log1p(rng.random(X.nnz) * 50.0)
    return X


def dense_loss(R: sp.csr_matrix, U: np.ndarray, Y: np.ndarray, reg: float, alpha: float) -> float:
    D = R.toarray()
    P = (D > 0).astype(float)
    C = 1.0 + alpha * D
    E = P - U @ Y.T
    return float(np.sum(C * E * E) + reg * (np.sum(U * U) + np.sum(Y * Y)))


def test_loss_matches_the_dense_objective() -> None:
    R = fixture()
    rng = np.random.default_rng(1)
    U, Y = rng.normal(size=(60, 5)), rng.normal(size=(40, 5))
    assert loss(R, U, Y, reg=0.3, alpha=4.0) == pytest.approx(
        dense_loss(R, U, Y, 0.3, 4.0), rel=1e-10
    )


def test_a_cholesky_step_solves_the_normal_equations_exactly() -> None:
    R = fixture()
    alpha, reg = 4.0, 0.3
    Y = np.random.default_rng(2).normal(size=(40, 6))
    C = R.copy()
    C.data = 1.0 + alpha * C.data
    U = solve_rows_cholesky(C, Y, reg)
    D = R.toarray()
    for u in range(0, 60, 7):
        c = 1.0 + alpha * D[u]
        p = (D[u] > 0).astype(float)
        A = Y.T @ (c[:, None] * Y) + reg * np.eye(6)
        expected = np.linalg.solve(A, Y.T @ (c * p))
        if p.any():
            assert np.max(np.abs(U[u] - expected)) < 1e-10
        else:
            assert np.all(U[u] == 0.0)


def test_cg_with_f_steps_reaches_the_exact_solution() -> None:
    R = fixture()
    C = R.copy()
    C.data = 1.0 + 4.0 * C.data
    Y = np.random.default_rng(3).normal(size=(40, 6))
    exact = solve_rows_cholesky(C, Y, 0.3)
    approx = solve_rows_cg(C, Y, 0.3, np.zeros((60, 6)), steps=12)
    assert np.max(np.abs(approx - exact)) < 1e-6


@pytest.mark.parametrize("solver", ["cholesky", "cg"])
def test_the_loss_falls_every_sweep(solver: str) -> None:
    model = ials(fixture(), factors=8, reg=0.1, alpha=5.0, sweeps=6, seed=9, solver=solver)  # type: ignore[arg-type]
    losses = model.losses
    assert len(losses) == 6
    assert all(b <= a * (1 + 1e-9) for a, b in itertools.pairwise(losses))


def test_training_is_reproducible_and_pure() -> None:
    R = fixture()
    before = R.copy()
    a = ials(R, factors=4, reg=0.1, alpha=2.0, sweeps=2, seed=11)
    b = ials(R, factors=4, reg=0.1, alpha=2.0, sweeps=2, seed=11)
    assert np.array_equal(a.item_factors, b.item_factors)
    assert (before != R).nnz == 0


def test_fold_in_is_the_user_step() -> None:
    R = fixture()
    model = ials(R, factors=5, reg=0.2, alpha=3.0, sweeps=3, seed=4, solver="cholesky")
    Y = model.item_factors
    C = R.copy()
    C.data = 1.0 + 3.0 * C.data
    rows = solve_rows_cholesky(C, Y, 0.2)
    u = 10
    start, stop = R.indptr[u], R.indptr[u + 1]
    history = list(zip(R.indices[start:stop].tolist(), R.data[start:stop].tolist(), strict=True))
    assert np.max(np.abs(fold_in(history, Y, reg=0.2, alpha=3.0) - rows[u])) < 1e-9
    assert np.all(fold_in([], Y, reg=0.2, alpha=3.0) == 0.0)


def test_ials_rejects_bad_input() -> None:
    R = fixture()
    with pytest.raises(ValueError, match="factors"):
        ials(R, factors=0, reg=0.1, alpha=1.0, sweeps=1, seed=0)
    with pytest.raises(ValueError, match="reg"):
        ials(R, factors=2, reg=0.0, alpha=1.0, sweeps=1, seed=0)
    with pytest.raises(ValueError, match="solver"):
        ials(R, factors=2, reg=0.1, alpha=1.0, sweeps=1, seed=0, solver="sgd")  # type: ignore[arg-type]
    bad = R.copy()
    bad.data[0] = -1.0
    with pytest.raises(ValueError, match="non-negative"):
        ials(bad, factors=2, reg=0.1, alpha=1.0, sweeps=1, seed=0)
