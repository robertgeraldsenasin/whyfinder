"""The pinned CI subsample `data-ci-v1`: a fixed, hash-chosen share of users (NFR-01, ADR-0003).

A user is in the sample when the first 32 bits of their (already salted and hashed) ID, read as a
fraction of 2³², fall below `fraction`. The choice depends only on the ID, so it never changes
between runs, machines or library versions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def in_subsample(users: pd.Series, fraction: float) -> pd.Series:
    """Boolean mask of users chosen for the subsample."""
    if not 0.0 < fraction <= 1.0:
        raise ValueError("fraction must be in (0, 1]")
    prefix = users.astype("str").str.slice(0, 8).map(lambda h: int(h, 16)).astype(np.float64)
    return (prefix / 2.0**32) < fraction


def subsample(tables: dict[str, pd.DataFrame], fraction: float) -> dict[str, pd.DataFrame]:
    """Keep the chosen users' rows in every table that has a `user` column."""
    return {
        name: df.loc[in_subsample(df["user"], fraction)].reset_index(drop=True)
        for name, df in tables.items()
    }
