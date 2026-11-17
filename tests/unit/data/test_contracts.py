from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from whyfinder.data.clean import hash_user
from whyfinder.data.contracts import ContractError, check_games, check_interactions


def interactions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "user": [hash_user("a", "s"), hash_user("b", "s")],
            "game": np.array([1, 2], dtype="int64"),
            "hours": [1.0, 0.0],
            "hours_missing": [False, True],
            "date": pd.to_datetime(["2016-01-01", None]).astype("datetime64[ns]"),
            "review_id": np.array([0, 1], dtype="int64"),
        }
    )


def games() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game": np.array([1, 2], dtype="int64"),
            "title": ["A", "B"],
            "price": [0.0, None],
            "release_year": pd.array([2016, None], dtype="Int64"),
        }
    )


def test_contracts_accept_good_tables() -> None:
    check_games(games())
    check_interactions(interactions(), games())


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda df: pd.concat([df, df.head(1)], ignore_index=True), "interactions"),
        (lambda df: df.assign(hours=[-1.0, 0.0]), "interactions"),
        (lambda df: df.assign(user=["short", "x"]), "interactions"),
        (lambda df: df.assign(extra=1), "interactions"),
        (lambda df: df.assign(game=np.array([1, 3], dtype="int64")), "missing from the catalogue"),
    ],
)
def test_interaction_contract_violations(change: object, message: str) -> None:
    assert callable(change)
    with pytest.raises(ContractError, match=message):
        check_interactions(change(interactions()), games())


def test_games_contract_rejects_duplicate_ids_and_negative_prices() -> None:
    with pytest.raises(ContractError, match="games"):
        check_games(games().assign(game=np.array([1, 1], dtype="int64")))
    with pytest.raises(ContractError, match="games"):
        check_games(games().assign(price=[-1.0, 0.0]))
