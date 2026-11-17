"""Global time split into train, validation and test, plus a cold-start set (FR-03, ADR-0002).

Cut-offs T1 < T2 are date quantiles of the interactions: train is everything before T1, validation
is [T1, T2), test is from T2 on. A validation or test row is kept only if its user has history in
train and its game appears in train (item-based models can't score unseen games). Users with 1 to
`cold_max` training interactions form the cold-start set instead.

If more than `max_missing_date` of rows lack a date, the split falls back to leave-last-out by
review order, as ADR-0002 prescribes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Split:
    """The four tables and a JSON-ready description of how they were made."""

    train: pd.DataFrame
    valid: pd.DataFrame
    test: pd.DataFrame
    cold: pd.DataFrame
    info: dict[str, object] = field(default_factory=dict)


def frame_hash(df: pd.DataFrame) -> str:
    """SHA-256 of a canonical CSV of (user, game, hours, date) sorted by (user, game)."""
    canonical = df[["user", "game", "hours", "date"]].sort_values(
        ["user", "game"], kind="mergesort"
    )
    text = canonical.to_csv(index=False, float_format="%.6f", date_format="%Y-%m-%d")
    return hashlib.sha256(text.encode()).hexdigest()


def _quantile_date(dates: pd.Series, q: float) -> pd.Timestamp:
    ordered = np.sort(dates.to_numpy())
    index = min(int(np.floor(q * len(ordered))), len(ordered) - 1)
    return pd.Timestamp(ordered[index])


def _finish(
    train: pd.DataFrame,
    valid_raw: pd.DataFrame,
    test_raw: pd.DataFrame,
    cold_max: int,
    info: dict[str, object],
) -> Split:
    counts = train["user"].value_counts()
    train_games = set(train["game"].unique().tolist())

    def route(part: pd.DataFrame, name: str) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
        n_train = part["user"].map(counts).fillna(0).astype("int64")
        known_game = part["game"].isin(list(train_games))
        warm = (n_train > cold_max) & known_game
        cold = (n_train >= 1) & (n_train <= cold_max) & known_game
        dropped = {
            f"{name}_dropped_no_train_history": int((n_train == 0).sum()),
            f"{name}_dropped_unseen_game": int(((n_train > 0) & ~known_game).sum()),
        }
        return part.loc[warm], part.loc[cold].assign(part=name), dropped

    valid, cold_valid, dropped_valid = route(valid_raw, "valid")
    test, cold_test, dropped_test = route(test_raw, "test")
    cold = pd.concat([cold_valid, cold_test], ignore_index=True)

    def tidy(df: pd.DataFrame) -> pd.DataFrame:
        return df.sort_values(["user", "game"], kind="mergesort").reset_index(drop=True)

    train, valid, test, cold = tidy(train), tidy(valid), tidy(test), tidy(cold)
    info = {
        **info,
        "cold_max_train_items": cold_max,
        **dropped_valid,
        **dropped_test,
        "rows": {"train": len(train), "valid": len(valid), "test": len(test), "cold": len(cold)},
        "users": {
            "train": int(train["user"].nunique()),
            "valid": int(valid["user"].nunique()),
            "test": int(test["user"].nunique()),
            "cold": int(cold["user"].nunique()),
        },
        "sha256": {
            "train": frame_hash(train),
            "valid": frame_hash(valid),
            "test": frame_hash(test),
            "cold": frame_hash(cold),
        },
    }
    return Split(train, valid, test, cold, info)


def time_split(
    df: pd.DataFrame,
    *,
    valid_quantile: float = 0.8,
    test_quantile: float = 0.9,
    cold_max: int = 4,
    max_missing_date: float = 0.10,
) -> Split:
    """Split interactions by global time cut-offs (or leave-last-out; see the module docstring)."""
    if not 0.0 < valid_quantile < test_quantile < 1.0:
        raise ValueError("need 0 < valid_quantile < test_quantile < 1")
    if df.empty:
        raise ValueError("cannot split an empty table")
    missing = float(df["date"].isna().mean())
    if missing > max_missing_date:
        return leave_last_out(df, cold_max=cold_max, missing_date_share=missing)

    dated = df.loc[df["date"].notna()]
    t1 = _quantile_date(dated["date"], valid_quantile)
    t2 = _quantile_date(dated["date"], test_quantile)
    if not t1 < t2:
        raise ValueError(f"cut-offs collapse (T1={t1:%Y-%m-%d}, T2={t2:%Y-%m-%d}); too few dates")
    train = dated.loc[dated["date"] < t1]
    valid = dated.loc[(dated["date"] >= t1) & (dated["date"] < t2)]
    test = dated.loc[dated["date"] >= t2]
    info: dict[str, object] = {
        "method": "global_time",
        "t1": f"{t1:%Y-%m-%d}",
        "t2": f"{t2:%Y-%m-%d}",
        "valid_quantile": valid_quantile,
        "test_quantile": test_quantile,
        "missing_date_share": missing,
        "dropped_missing_date": int(len(df) - len(dated)),
    }
    return _finish(train, valid, test, cold_max, info)


def leave_last_out(df: pd.DataFrame, *, cold_max: int = 4, missing_date_share: float) -> Split:
    """Per user, by review order: last interaction → test, second last → validation."""
    ordered = df.sort_values(["user", "review_id"], kind="mergesort")
    position_from_end = ordered.groupby("user").cumcount(ascending=False)
    test = ordered.loc[position_from_end == 0]
    valid = ordered.loc[position_from_end == 1]
    train = ordered.loc[position_from_end >= 2]
    info: dict[str, object] = {
        "method": "leave_last_out",
        "t1": None,
        "t2": None,
        "missing_date_share": missing_date_share,
        "dropped_missing_date": 0,
    }
    return _finish(train, valid, test, cold_max, info)
