"""Data contracts (docs/spec/03_DATA.md), checked after every stage that writes a table.

Schemas are Pandera; the cross-table rules (k-core, split monotonicity, history) are plain checks
that raise `ContractError` with a message saying exactly what broke.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa


class ContractError(ValueError):
    """A table broke its contract."""


INTERACTIONS = pa.DataFrameSchema(
    {
        "user": pa.Column(str, pa.Check.str_length(16, 16)),
        "game": pa.Column("int64", pa.Check.ge(0)),
        "hours": pa.Column("float64", pa.Check.ge(0.0)),
        "hours_missing": pa.Column(bool),
        "date": pa.Column("datetime64[ns]", nullable=True),
        "review_id": pa.Column("int64", pa.Check.ge(0)),
    },
    unique=["user", "game"],
    strict=True,
    coerce=False,
)

GAMES = pa.DataFrameSchema(
    {
        "game": pa.Column("int64", pa.Check.ge(0), unique=True),
        "title": pa.Column(str),
        "price": pa.Column("float64", pa.Check.ge(0.0), nullable=True),
        "release_year": pa.Column("Int64", nullable=True),
    },
    strict=False,
    coerce=False,
)


def _validate(schema: pa.DataFrameSchema, df: pd.DataFrame, name: str) -> None:
    try:
        schema.validate(df, lazy=True)
    except (pa.errors.SchemaErrors, pa.errors.SchemaError) as error:
        raise ContractError(f"{name}: {error}") from error


def check_games(games: pd.DataFrame) -> None:
    """Catalogue: unique non-negative IDs, a title for every game, prices ≥ 0."""
    _validate(GAMES, games, "games")


def check_interactions(df: pd.DataFrame, games: pd.DataFrame) -> None:
    """Interactions: schema, unique (user, game), hours ≥ 0, every game in the catalogue."""
    _validate(INTERACTIONS, df, "interactions")
    unknown = set(df["game"].unique().tolist()) - set(games["game"].tolist())
    if unknown:
        raise ContractError(f"interactions: {len(unknown)} games missing from the catalogue")


def check_kcore(df: pd.DataFrame, k: int) -> None:
    """Every user and every game has at least k interactions."""
    if df.empty:
        raise ContractError("k-core: no interactions left")
    low_users = int((df["user"].value_counts() < k).sum())
    low_games = int((df["game"].value_counts() < k).sum())
    if low_users or low_games:
        raise ContractError(f"k-core: {low_users} users and {low_games} games below k={k}")
