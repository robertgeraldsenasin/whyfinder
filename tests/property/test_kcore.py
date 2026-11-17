from __future__ import annotations

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from whyfinder.data.contracts import ContractError, check_kcore
from whyfinder.data.kcore import kcore

edges = st.lists(
    st.tuples(st.integers(0, 12), st.integers(0, 9)), min_size=0, max_size=80, unique=True
)


def frame(pairs: list[tuple[int, int]]) -> pd.DataFrame:
    return pd.DataFrame(pairs, columns=["user", "game"]).astype("int64")


def naive_kcore(pairs: list[tuple[int, int]], k: int) -> set[tuple[int, int]]:
    """Remove one under-degree vertex at a time; the fixed point is the same maximal k-core."""
    current = set(pairs)
    while True:
        users: dict[int, int] = {}
        games: dict[int, int] = {}
        for u, g in current:
            users[u] = users.get(u, 0) + 1
            games[g] = games.get(g, 0) + 1
        low_user = next((u for u, c in sorted(users.items()) if c < k), None)
        if low_user is not None:
            current = {(u, g) for u, g in current if u != low_user}
            continue
        low_game = next((g for g, c in sorted(games.items()) if c < k), None)
        if low_game is None:
            return current
        current = {(u, g) for u, g in current if g != low_game}


@settings(max_examples=150, deadline=None)
@given(edges, st.integers(1, 4))
def test_kcore_is_the_maximal_k_core(pairs: list[tuple[int, int]], k: int) -> None:
    df = frame(pairs)
    core, passes = kcore(df, k)
    assert passes >= 1
    assert set(map(tuple, core[["user", "game"]].to_numpy().tolist())) == naive_kcore(pairs, k)
    if len(core):
        assert core["user"].value_counts().min() >= k
        assert core["game"].value_counts().min() >= k
        check_kcore(core, k)
    again, _ = kcore(core, k)
    assert again.equals(core)  # idempotent
    assert df.equals(frame(pairs))  # input untouched


def test_kcore_rejects_k_below_one() -> None:
    with pytest.raises(ValueError, match="k must be"):
        kcore(frame([(1, 1)]), 0)


def test_check_kcore_reports_violations() -> None:
    with pytest.raises(ContractError, match="no interactions"):
        check_kcore(frame([]), 2)
    with pytest.raises(ContractError, match="below k=2"):
        check_kcore(frame([(1, 1), (1, 2), (2, 1)]), 2)
