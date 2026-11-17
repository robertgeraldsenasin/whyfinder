from __future__ import annotations

import pandas as pd
import pytest

from whyfinder.data.clean import clean_games, clean_interactions, hash_user, parse_dates


def reviews(rows: list[tuple[object, ...]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["review_id", "username", "game", "hours", "date"]).astype(
        {"game": "Int64", "hours": "float64"}
    )


def test_parse_dates_accepts_known_formats_and_marks_the_rest() -> None:
    raw = pd.Series(["2017-12-17", "December 2, 2017", "Dec 2, 2017", "soon", None])
    parsed = parse_dates(raw)
    assert parsed.iloc[0] == pd.Timestamp("2017-12-17")
    assert parsed.iloc[1] == parsed.iloc[2] == pd.Timestamp("2017-12-02")
    assert parsed.iloc[3:].isna().all()


def test_hash_user_is_salted_and_stable() -> None:
    a = hash_user("alice", "s1")
    assert a == hash_user("alice", "s1")
    assert a != hash_user("alice", "s2")
    assert len(a) == 16
    assert int(a, 16) >= 0


def test_clean_interactions_drops_dedupes_and_clips() -> None:
    df = reviews(
        [
            (0, "alice", 1, 2.0, "2016-01-01"),
            (1, "alice", 1, 50.0, "2016-02-01"),  # duplicate: more hours wins
            (2, "alice", 2, None, "2016-03-01"),  # no hours → 0, flagged
            (3, None, 1, 1.0, "2016-01-01"),  # no user
            (4, "bob", None, 1.0, "2016-01-01"),  # no game
            (5, "bob", 9, 1.0, "2016-01-01"),  # unknown game
            (6, "bob", 2, 1e6, "later"),  # clipped, undated
        ]
    )
    out, stats = clean_interactions(df, {1, 2}, salt="s", clip_quantile=0.5)
    assert list(out.columns) == ["user", "game", "hours", "hours_missing", "date", "review_id"]
    assert stats.rows_in == 7
    assert (stats.dropped_no_user, stats.dropped_no_game, stats.dropped_unknown_game) == (1, 1, 1)
    assert stats.duplicates_removed == 1
    assert stats.rows_out == len(out) == 3
    alice = out[out["user"] == hash_user("alice", "s")].set_index("game")
    assert alice.loc[1, "review_id"] == 1
    assert alice.loc[2, "hours"] == 0.0
    assert bool(alice.loc[2, "hours_missing"])
    assert out["hours"].max() == stats.hours_clip
    assert stats.date_coverage == pytest.approx(2 / 3)
    assert stats.hours_coverage == pytest.approx(2 / 3)
    assert (stats.date_min, stats.date_max) == ("2016-02-01", "2016-03-01")
    assert out.equals(out.sort_values(["user", "game"]).reset_index(drop=True))


def test_clean_interactions_rejects_bad_quantile() -> None:
    with pytest.raises(ValueError, match="clip_quantile"):
        clean_interactions(reviews([]), set(), salt="s", clip_quantile=0.0)


def test_clean_interactions_on_empty_input() -> None:
    out, stats = clean_interactions(reviews([]), {1}, salt="s")
    assert out.empty
    assert stats.date_coverage == 0.0
    assert stats.date_min is None


def test_clean_games_adds_year_and_title() -> None:
    games = pd.DataFrame(
        {
            "game": [2, 1, 2],
            "title": [None, "One", "dup"],
            "release_date": ["Mar 3, 2017", "soon", "2018"],
            "genres": [["A"], None, []],
            "tags": [["t"], ["u"], []],
            "specs": [[], [], []],
        }
    )
    out = clean_games(games)
    assert out["game"].tolist() == [1, 2]
    assert out["title"].tolist() == ["One", "App 2"]
    assert out["release_year"].isna().tolist() == [True, False]
    assert out.loc[1, "release_year"] == 2017
    assert out.loc[0, "genres"] == []
