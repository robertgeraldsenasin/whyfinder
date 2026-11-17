"""k-core filtering of the user–game bipartite graph (FR-02)."""

from __future__ import annotations

import pandas as pd


def kcore(
    df: pd.DataFrame, k: int, user: str = "user", item: str = "game"
) -> tuple[pd.DataFrame, int]:
    """The largest subset in which every user and every game has at least `k` interactions.

    Repeatedly drops users and games below `k` until nothing changes. The result is unique (it is
    the maximal k-core), so the removal order doesn't matter. Returns the rows kept, in their
    original order, and the number of passes.
    """
    if k < 1:
        raise ValueError("k must be at least 1")
    passes = 0
    while True:
        passes += 1
        users = df[user].value_counts()
        items = df[item].value_counts()
        low_users = users.index[users < k]
        low_items = items.index[items < k]
        if len(low_users) == 0 and len(low_items) == 0:
            return df, passes
        df = df.loc[~df[user].isin(low_users) & ~df[item].isin(low_items)]
