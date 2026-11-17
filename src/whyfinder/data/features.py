"""The training matrix X (users × games) with confidence weights and the item cap.

FR-02, ADR-0004.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import scipy.sparse as sp


@dataclass(frozen=True)
class Features:
    """X_train and the index tables that give its rows and columns meaning."""

    X: sp.csr_matrix
    users: pd.DataFrame  # columns: row, user
    items: pd.DataFrame  # columns: col, game, train_count


def confidence(hours: np.ndarray, alpha: float, eps: float) -> np.ndarray:
    """x = 1 + α·log(1 + hours/ε): 1 for a review with no hours, growing slowly with play time."""
    if alpha < 0 or eps <= 0:
        raise ValueError("need alpha ≥ 0 and eps > 0")
    return 1.0 + alpha * np.log1p(np.asarray(hours, dtype=np.float64) / eps)


def build_features(train: pd.DataFrame, *, item_cap: int, alpha: float, eps: float) -> Features:
    """Keep the `item_cap` games with the most train interactions (ties by game ID), then build X.

    Rows are users sorted by ID; columns are the kept games sorted by ID.
    """
    if item_cap < 1:
        raise ValueError("item_cap must be at least 1")
    counts = train.groupby("game").size().rename("train_count").reset_index()
    counts = counts.sort_values(["train_count", "game"], ascending=[False, True], kind="mergesort")
    kept = counts.head(item_cap).sort_values("game", kind="mergesort").reset_index(drop=True)
    kept.insert(0, "col", np.arange(len(kept), dtype=np.int64))

    rows = train.loc[train["game"].isin(kept["game"].tolist())]
    users = pd.DataFrame({"user": np.sort(rows["user"].unique())})
    users.insert(0, "row", np.arange(len(users), dtype=np.int64))

    row_index = pd.Series(users["row"].to_numpy(), index=users["user"].to_numpy())
    col_index = pd.Series(kept["col"].to_numpy(), index=kept["game"].to_numpy())
    r = row_index.loc[rows["user"].to_numpy()].to_numpy()
    c = col_index.loc[rows["game"].to_numpy()].to_numpy()
    values = confidence(rows["hours"].to_numpy(), alpha, eps)
    X = sp.csr_matrix((values, (r, c)), shape=(len(users), len(kept)), dtype=np.float64)
    X.sort_indices()
    return Features(X=X, users=users, items=kept)
