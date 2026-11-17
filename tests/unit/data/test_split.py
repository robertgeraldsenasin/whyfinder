from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from whyfinder.data.contracts import ContractError, check_split
from whyfinder.data.split import frame_hash, time_split


def interactions(n_users: int = 30, n_games: int = 8, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    review_id = 0
    for u in range(n_users):
        for g in rng.choice(n_games, size=rng.integers(4, n_games + 1), replace=False):
            day = pd.Timestamp("2016-01-01") + pd.Timedelta(days=int(rng.integers(0, 1000)))
            rows.append((f"{u:016x}", int(g), float(rng.integers(0, 100)), day, review_id))
            review_id += 1
    df = pd.DataFrame(rows, columns=["user", "game", "hours", "date", "review_id"])
    df["hours_missing"] = False
    return df


def test_global_time_split_respects_cutoffs_and_history() -> None:
    df = interactions()
    split = time_split(df, valid_quantile=0.7, test_quantile=0.85, cold_max=2)
    info = split.info
    assert info["method"] == "global_time"
    t1, t2 = pd.Timestamp(str(info["t1"])), pd.Timestamp(str(info["t2"]))
    assert split.train["date"].max() < t1 <= split.valid["date"].min()
    assert split.valid["date"].max() < t2 <= split.test["date"].min()
    counts = split.train["user"].value_counts()
    assert (split.valid["user"].map(counts) > 2).all()
    assert (split.test["user"].map(counts) > 2).all()
    if len(split.cold):
        cold_counts = split.cold["user"].map(counts)
        assert cold_counts.between(1, 2).all()
        assert set(split.cold["part"]) <= {"valid", "test"}
    check_split(
        split.train, split.valid, split.test, t1=str(info["t1"]), t2=str(info["t2"]), cold_max=2
    )
    rows = info["rows"]
    assert isinstance(rows, dict)
    assert rows["train"] == len(split.train)
    sha = info["sha256"]
    assert isinstance(sha, dict)
    assert sha["test"] == frame_hash(split.test)


def test_split_drops_games_unseen_in_train() -> None:
    df = interactions()
    late = pd.DataFrame(
        {
            "user": [df["user"].iloc[0]],
            "game": [77],
            "hours": [1.0],
            "date": [pd.Timestamp("2030-01-01")],
            "review_id": [10_000],
            "hours_missing": [False],
        }
    )
    split = time_split(pd.concat([df, late], ignore_index=True), cold_max=1)
    assert 77 not in set(split.test["game"]) | set(split.cold["game"])
    assert split.info["test_dropped_unseen_game"] == 1


def test_split_falls_back_to_leave_last_out_when_dates_are_missing() -> None:
    df = interactions()
    df.loc[df.index % 3 == 0, "date"] = pd.NaT
    split = time_split(df, cold_max=1)
    assert split.info["method"] == "leave_last_out"
    assert split.info["t1"] is None
    last = df.sort_values("review_id").groupby("user").tail(1)
    assert set(zip(split.test["user"], split.test["game"], strict=True)) <= set(
        zip(last["user"], last["game"], strict=True)
    )
    check_split(split.train, split.valid, split.test, t1=None, t2=None, cold_max=1)


@pytest.mark.parametrize(("v", "t"), [(0.0, 0.5), (0.9, 0.8), (0.5, 1.0)])
def test_split_rejects_bad_quantiles(v: float, t: float) -> None:
    with pytest.raises(ValueError, match="quantile"):
        time_split(interactions(), valid_quantile=v, test_quantile=t)


def test_split_rejects_empty_and_collapsed_inputs() -> None:
    with pytest.raises(ValueError, match="empty"):
        time_split(interactions().iloc[:0])
    same_day = interactions().assign(date=pd.Timestamp("2017-01-01"))
    with pytest.raises(ValueError, match="collapse"):
        time_split(same_day)


def test_frame_hash_ignores_row_order() -> None:
    df = interactions()
    assert frame_hash(df) == frame_hash(df.sample(frac=1.0, random_state=1))
    assert frame_hash(df) != frame_hash(df.iloc[1:])


def test_check_split_catches_leaks_and_missing_history() -> None:
    split = time_split(interactions(), cold_max=2)
    t1, t2 = str(split.info["t1"]), str(split.info["t2"])
    with pytest.raises(ContractError, match="not before"):
        check_split(split.train, split.valid, split.test, t1=t2, t2=t1, cold_max=2)
    leaked = pd.concat([split.train, split.test.head(1)])
    with pytest.raises(ContractError, match="on or after T1"):
        check_split(leaked, split.valid, split.test, t1=t1, t2=t2, cold_max=2)
    with pytest.raises(ContractError, match="outside"):
        check_split(split.train, split.test.head(1), split.test, t1=t1, t2=t2, cold_max=2)
    with pytest.raises(ContractError, match="predates"):
        check_split(split.train, split.valid, split.valid.head(1), t1=t1, t2=t2, cold_max=2)
    with pytest.raises(ContractError, match="train interactions"):
        check_split(split.train, split.valid, split.test, t1=t1, t2=t2, cold_max=1000)
    unseen = split.valid.head(1).assign(game=99)
    with pytest.raises(ContractError, match="never seen"):
        check_split(split.train, unseen, split.test, t1=t1, t2=t2, cold_max=2)
