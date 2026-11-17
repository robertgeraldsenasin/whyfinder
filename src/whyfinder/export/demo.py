"""The demo slice (ADR-0015): the most-played games with everything the browser engine needs.

The slice holds aggregates only: the co-play Gram matrix G = XᵀX over the slice's games (binary
train interactions), game metadata and a 2-D layout for the star map. No user rows, no review text.

G is stored as its packed upper triangle, row by row: entries (0,0), (0,1), …, (0,n−1), (1,1), …
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import scipy.sparse as sp

SLICE_VERSION = 1


def top_games(train: pd.DataFrame, n_games: int) -> pd.DataFrame:
    """The `n_games` games with the most train interactions; ties by game ID; sorted by ID."""
    if n_games < 2:
        raise ValueError("a slice needs at least 2 games")
    counts = train.groupby("game").size().rename("train_count").reset_index()
    counts = counts.sort_values(["train_count", "game"], ascending=[False, True], kind="mergesort")
    return counts.head(n_games).sort_values("game", kind="mergesort").reset_index(drop=True)


def gram(train: pd.DataFrame, games: np.ndarray) -> tuple[np.ndarray, int]:
    """G = XᵀX over `games` for binary X (users × games); also the number of users involved."""
    rows = train.loc[train["game"].isin(games.tolist()), ["user", "game"]].drop_duplicates()
    users, user_index = np.unique(rows["user"].to_numpy(), return_inverse=True)
    col = pd.Series(np.arange(len(games)), index=games).loc[rows["game"].to_numpy()].to_numpy()
    X = sp.csr_matrix(
        (np.ones(len(rows), dtype=np.int64), (user_index, col)), shape=(len(users), len(games))
    )
    G = (X.T @ X).toarray().astype(np.int64)
    return G, len(users)


def pack_upper(G: np.ndarray) -> list[int]:
    """Row-major upper triangle including the diagonal."""
    rows, cols = np.triu_indices(G.shape[0])
    return [int(v) for v in G[rows, cols]]


def unpack_upper(packed: list[int], n: int) -> np.ndarray:
    """Inverse of `pack_upper`: the full symmetric matrix."""
    if len(packed) != n * (n + 1) // 2:
        raise ValueError(f"packed length {len(packed)} does not fit n={n}")
    G = np.zeros((n, n), dtype=np.int64)
    rows, cols = np.triu_indices(n)
    G[rows, cols] = packed
    G[cols, rows] = packed
    return G


def cosine(G: np.ndarray) -> np.ndarray:
    """Co-play cosine S_ij = G_ij / √(G_ii G_jj), zero diagonal."""
    d = np.sqrt(np.maximum(np.diag(G).astype(np.float64), 1.0))
    S = G / np.outer(d, d)
    np.fill_diagonal(S, 0.0)
    return np.asarray(S, dtype=np.float64)


def layout(S: np.ndarray, *, neighbors: int, iterations: int) -> np.ndarray:
    """Deterministic 2-D positions in [0.04, 0.96]² where co-played games sit close together.

    Spectral start (two leading non-trivial eigenvectors of the normalised similarity, signs fixed),
    then force-directed refinement: springs to each game's `neighbors` most similar games, soft
    repulsion between all pairs, a step size that cools linearly. No randomness.
    """
    n = S.shape[0]
    if n < 3:
        return np.tile([0.5, 0.5], (n, 1)) + np.arange(n)[:, None] * [0.1, 0.0]
    degree = np.maximum(S.sum(axis=1), 1e-12)
    norm = S / np.sqrt(np.outer(degree, degree))
    _, vectors = np.linalg.eigh(norm)
    pos = vectors[:, -3:-1][:, ::-1].copy()
    for k in range(2):
        pivot = int(np.argmax(np.abs(pos[:, k])))
        if pos[pivot, k] < 0:
            pos[:, k] = -pos[:, k]
    pos = (pos - pos.mean(axis=0)) / (pos.std(axis=0) + 1e-12)

    k = min(neighbors, n - 1)
    order = np.argsort(-S, axis=1, kind="stable")[:, :k]
    springs = np.zeros_like(S)
    rows = np.repeat(np.arange(n), k)
    springs[rows, order.ravel()] = S[rows, order.ravel()]
    springs = np.maximum(springs, springs.T)
    springs /= springs.max() if springs.max() > 0 else 1.0

    ideal = 1.0 / np.sqrt(n)
    for step in range(iterations):
        delta = pos[:, None, :] - pos[None, :, :]
        dist2 = (delta**2).sum(axis=2) + 1e-4
        repulse = (ideal**2 / dist2)[:, :, None] * delta
        attract = -(springs * np.sqrt(dist2) / ideal)[:, :, None] * delta
        force = (repulse + attract).sum(axis=1)
        length = np.linalg.norm(force, axis=1, keepdims=True) + 1e-12
        temperature = 0.1 * (1.0 - step / iterations) + 0.002
        pos = pos + force / length * np.minimum(length, temperature)

    lo, hi = np.percentile(pos, 1, axis=0), np.percentile(pos, 99, axis=0)
    pos = np.clip((pos - lo) / np.maximum(hi - lo, 1e-12), 0.0, 1.0)
    return np.asarray(0.04 + 0.92 * pos, dtype=np.float64)


def _clean_value(value: object) -> Any:
    if value is None or (isinstance(value, float) and np.isnan(value)) or value is pd.NA:
        return None
    return value


def demo_slice(
    train: pd.DataFrame,
    games: pd.DataFrame,
    *,
    n_games: int,
    tags_per_game: int,
    neighbors: int,
    iterations: int,
    split: dict[str, Any],
) -> dict[str, Any]:
    """Build the slice as a JSON-ready dict."""
    top = top_games(train, n_games)
    ids = top["game"].to_numpy()
    G, n_users = gram(train, ids)
    S = cosine(G)
    pos = layout(S, neighbors=neighbors, iterations=iterations)
    meta = games.set_index("game").loc[ids]
    plays = top["train_count"].to_numpy(dtype=np.int64)
    records = []
    for i, game in enumerate(ids):
        row = meta.loc[game]
        year = _clean_value(row.get("release_year"))
        price = _clean_value(row.get("price"))
        records.append(
            {
                "id": int(game),
                "title": str(row["title"]),
                "developer": _clean_value(row.get("developer")),
                "publisher": _clean_value(row.get("publisher")),
                "tags": [str(t) for t in list(row.get("tags", []))[:tags_per_game]],
                "genres": [str(t) for t in list(row.get("genres", []))],
                "year": int(year) if year is not None else None,
                "price": round(float(price), 2) if price is not None else None,
                "plays": int(plays[i]),
                "x": round(float(pos[i, 0]), 5),
                "y": round(float(pos[i, 1]), 5),
            }
        )
    return {
        "version": SLICE_VERSION,
        "source": "UCSD McAuley Lab Steam datasets (Version 2 reviews), train split only",
        "split": {"t1": split.get("t1"), "method": split.get("method")},
        "users": n_users,
        "games": records,
        "gram": {"n": len(ids), "packed_upper": pack_upper(G)},
    }
