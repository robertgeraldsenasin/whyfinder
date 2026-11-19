"""iALS, the latent-factor rival (FR-09; Hu, Koren & Volinsky, ICDM 2008).

Every observed (u, i) has preference p = 1 and confidence c = 1 + α·r, where r is the entry of X
(the hours-based weight); every other pair has p = 0 and c = 1. The loss is

    L = Σ_{u,i} c_ui (p_ui − x_uᵀ y_i)² + λ (Σ_u ‖x_u‖² + Σ_i ‖y_i‖²)

and alternating least squares solves one side exactly while the other is fixed:

    x_u = (YᵀY + Yᵀ(Cᵘ − I)Y + λI)⁻¹ Yᵀ Cᵘ p(u)

Two solvers. `cholesky` factors each user's (and game's) f × f system: exact, one row at a time.
`cg` runs a few conjugate-gradient steps for every row at once, warm-started from the current
factors (Takács, Pilászy & Tikk, RecSys 2011); with f steps it reaches the exact solution, and three
are usually enough. Seeds fix the initial factors, so runs are reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp

Solver = Literal["cholesky", "cg"]
_CHUNK = 400_000  # interactions per block in the batched products (bounds memory)


@dataclass(frozen=True)
class Ials:
    """Trained factors and the loss after each sweep (one sweep = users, then games)."""

    user_factors: np.ndarray
    item_factors: np.ndarray
    losses: list[float] = field(default_factory=list)


def _confidence(R: sp.csr_matrix, alpha: float) -> sp.csr_matrix:
    C = R.copy().tocsr()
    C.data = 1.0 + alpha * np.asarray(C.data, dtype=np.float64)
    return C


def loss(R: sp.csr_matrix, U: np.ndarray, Y: np.ndarray, *, reg: float, alpha: float) -> float:
    """The iALS objective, without forming the dense m × n prediction matrix.

    Σ over all pairs of (x_uᵀy_i)² is trace((UᵀU)(YᵀY)); observed pairs then add c(1 − s)² − s².
    """
    C = _confidence(R, alpha)
    rows = np.repeat(np.arange(C.shape[0]), np.diff(C.indptr))
    total = float(np.sum((U.T @ U) * (Y.T @ Y)))
    for start in range(0, C.nnz, _CHUNK):
        stop = min(start + _CHUNK, C.nnz)
        s = np.einsum("nf,nf->n", U[rows[start:stop]], Y[C.indices[start:stop]])
        c = C.data[start:stop]
        total += float(np.sum(c * (1.0 - s) ** 2 - s * s))
    return total + reg * float(np.sum(U * U) + np.sum(Y * Y))


def solve_rows_cholesky(C: sp.csr_matrix, Y: np.ndarray, reg: float) -> np.ndarray:
    """Exact least squares for every row of C (confidences), the other side's factors Y fixed."""
    f = Y.shape[1]
    base = Y.T @ Y + reg * np.eye(f)
    out = np.zeros((C.shape[0], f), dtype=np.float64)
    for u in range(C.shape[0]):
        start, stop = C.indptr[u], C.indptr[u + 1]
        if start == stop:
            continue
        cols = C.indices[start:stop]
        c = C.data[start:stop]
        Yi = Y[cols]
        A = base + (Yi.T * (c - 1.0)) @ Yi
        b = Yi.T @ c
        out[u] = la.cho_solve(
            la.cho_factor(A, lower=True, check_finite=False), b, check_finite=False
        )
    return out


def _apply(
    C: sp.csr_matrix, rows: np.ndarray, Y: np.ndarray, base: np.ndarray, V: np.ndarray
) -> np.ndarray:
    """A_u v_u for every row u at once: (YᵀY + λI) v_u + Σ_i (c_ui − 1) y_i (y_iᵀ v_u)."""
    out = V @ base
    weights = np.empty(C.nnz, dtype=np.float64)
    for start in range(0, C.nnz, _CHUNK):
        stop = min(start + _CHUNK, C.nnz)
        dots = np.einsum("nf,nf->n", Y[C.indices[start:stop]], V[rows[start:stop]])
        weights[start:stop] = (C.data[start:stop] - 1.0) * dots
    W = sp.csr_matrix((weights, C.indices, C.indptr), shape=C.shape)
    return np.asarray(out + np.asarray(W @ Y), dtype=np.float64)


def solve_rows_cg(
    C: sp.csr_matrix, Y: np.ndarray, reg: float, V0: np.ndarray, steps: int
) -> np.ndarray:
    """`steps` conjugate-gradient steps for every row at once, warm-started from V0."""
    f = Y.shape[1]
    base = Y.T @ Y + reg * np.eye(f)
    rows = np.repeat(np.arange(C.shape[0]), np.diff(C.indptr))
    b = np.asarray(C @ Y)
    V = np.array(V0, dtype=np.float64)
    r = b - _apply(C, rows, Y, base, V)
    p = r.copy()
    rs = np.einsum("uf,uf->u", r, r)
    for _ in range(steps):
        Ap = _apply(C, rows, Y, base, p)
        pAp = np.einsum("uf,uf->u", p, Ap)
        step = np.divide(rs, pAp, out=np.zeros_like(rs), where=pAp > 0.0)
        V += step[:, None] * p
        r -= step[:, None] * Ap
        rs_new = np.einsum("uf,uf->u", r, r)
        beta = np.divide(rs_new, rs, out=np.zeros_like(rs), where=rs > 0.0)
        p = r + beta[:, None] * p
        rs = rs_new
    return np.asarray(V, dtype=np.float64)


def ials(
    R: sp.csr_matrix,
    *,
    factors: int,
    reg: float,
    alpha: float,
    sweeps: int,
    seed: int,
    solver: Solver = "cholesky",
    cg_steps: int = 3,
    track_loss: bool = True,
) -> Ials:
    """Train on R (users × games, non-negative weights). Pure: R is not modified."""
    if factors < 1 or sweeps < 1:
        raise ValueError("need factors ≥ 1 and sweeps ≥ 1")
    if reg <= 0 or alpha < 0:
        raise ValueError("need reg > 0 and alpha ≥ 0")
    if solver not in ("cholesky", "cg"):
        raise ValueError(f"unknown solver {solver!r}")
    R = sp.csr_matrix(R, dtype=np.float64)
    if R.nnz and float(R.data.min()) < 0.0:
        raise ValueError("weights must be non-negative")
    rng = np.random.default_rng(seed)
    m, n = R.shape
    U = rng.normal(0.0, 0.01, (m, factors))
    Y = rng.normal(0.0, 0.01, (n, factors))
    C = _confidence(R, alpha)
    Ct = C.T.tocsr()
    losses: list[float] = []
    for _ in range(sweeps):
        if solver == "cholesky":
            U = solve_rows_cholesky(C, Y, reg)
            Y = solve_rows_cholesky(Ct, U, reg)
        else:
            U = solve_rows_cg(C, Y, reg, U, cg_steps)
            Y = solve_rows_cg(Ct, U, reg, Y, cg_steps)
        if track_loss:
            losses.append(loss(R, U, Y, reg=reg, alpha=alpha))
    return Ials(user_factors=U, item_factors=Y, losses=losses)


def fold_in(
    history: list[tuple[int, float]], Y: np.ndarray, *, reg: float, alpha: float
) -> np.ndarray:
    """A user's factor from their history of (game index, weight), with the games' factors fixed.

    The same exact solve as a training step, so a user seen in training gets the factor the next
    sweep would give them.
    """
    f = Y.shape[1]
    if not history:
        return np.zeros(f, dtype=np.float64)
    cols = np.array([j for j, _ in history], dtype=np.int64)
    c = 1.0 + alpha * np.array([w for _, w in history], dtype=np.float64)
    Yi = Y[cols]
    A = Y.T @ Y + reg * np.eye(f) + (Yi.T * (c - 1.0)) @ Yi
    return np.asarray(la.solve(A, Yi.T @ c, assume_a="pos"), dtype=np.float64)
