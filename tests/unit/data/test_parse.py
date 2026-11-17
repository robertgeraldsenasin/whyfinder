from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tests.conftest import write_gz
from whyfinder.data.parse import (
    ParseError,
    ParseStats,
    game_row,
    iter_records,
    parse_games,
    parse_line,
    parse_reviews,
    review_row,
)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (b"{'a': 1, 'b': True, 'c': None}", {"a": 1, "b": True, "c": None}),
        (b"  {'t': 'it\\'s'}\n", {"t": "it's"}),
        (b"[1, 2]", None),  # not a dict
        (b"{'a': ", None),  # truncated
        (b"__import__('os').system('true')", None),  # never evaluated
        (b"   ", None),
    ],
)
def test_parse_line(line: bytes, expected: object) -> None:
    assert parse_line(line) == expected


def test_parse_reviews_counts_and_links_text(raw_dir: Path, tmp_path: Path) -> None:
    stats = parse_reviews(
        raw_dir / "steam_reviews.json.gz",
        tmp_path / "reviews.parquet",
        tmp_path / "text.parquet",
        tolerance=0.01,
    )
    reviews = pd.read_parquet(tmp_path / "reviews.parquet")
    text = pd.read_parquet(tmp_path / "text.parquet")
    assert stats.malformed == 1
    assert stats.written == stats.lines - 1 == len(reviews)
    assert 0 < stats.malformed_share < 0.01
    assert reviews["review_id"].is_monotonic_increasing
    assert set(text["review_id"]) <= set(reviews["review_id"])
    assert reviews["username"].isna().sum() == 1
    assert reviews["hours"].isna().any()


def test_parse_reviews_fails_above_tolerance(raw_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(ParseError, match="malformed"):
        parse_reviews(
            raw_dir / "steam_reviews.json.gz",
            tmp_path / "r.parquet",
            tmp_path / "t.parquet",
            tolerance=0.0001,
        )


def test_parallel_parse_equals_serial(raw_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = raw_dir / "steam_reviews.json.gz"
    serial = list(iter_records(path, workers=1))
    monkeypatch.setattr("whyfinder.data.parse.BATCH_LINES", 7)  # many batches: exercise the window
    assert list(iter_records(path, workers=2)) == serial


def test_iter_records_rejects_zero_workers(raw_dir: Path) -> None:
    with pytest.raises(ValueError, match="workers"):
        next(iter_records(raw_dir / "steam_reviews.json.gz", workers=0))


def test_iter_records_reads_plain_text_and_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "plain.json"
    path.write_text("{'a': 1}\n\n{'a': 2}\n")
    assert list(iter_records(path)) == [{"a": 1}, {"a": 2}]


def test_review_row_normalises_types() -> None:
    row = review_row(5, {"username": " x ", "product_id": "42", "hours": "3.5", "user_id": 7})
    assert row == {
        "review_id": 5,
        "username": "x",
        "steam_user_id": "7",
        "game": 42,
        "hours": 3.5,
        "date": None,
        "early_access": None,
        "found_funny": None,
    }
    assert review_row(0, {"product_id": "abc", "hours": float("nan")})["game"] is None
    assert review_row(0, {"hours": True})["hours"] is None


def test_game_row_handles_prices_lists_and_missing_ids() -> None:
    assert game_row({"title": "no id"}) is None
    free = game_row({"id": "3", "app_name": "A", "price": "Free to Play", "developer": ["X", "Y"]})
    assert free is not None
    assert free["title"] == "A"
    assert free["price"] == 0.0
    assert free["developer"] == "X, Y"
    unknown_price = game_row({"id": "4", "title": "B", "price": "Starting at $1", "tags": "x"})
    assert unknown_price is not None
    assert unknown_price["price"] is None
    assert unknown_price["tags"] == []


def test_parse_games_skips_missing_ids_and_keeps_first_duplicate(
    raw_dir: Path, tmp_path: Path
) -> None:
    stats = parse_games(raw_dir / "steam_games.json.gz", tmp_path / "g.parquet")
    games = pd.read_parquet(tmp_path / "g.parquet")
    assert stats == ParseStats(lines=17, malformed=0, written=15)
    assert games.loc[games["game"] == 10, "title"].item() == "Game 10"
    assert games.loc[games["game"] == 12, "price"].item() == 0.0


def test_parse_games_writes_an_empty_table_for_an_empty_file(tmp_path: Path) -> None:
    raw = write_gz(tmp_path / "empty.json.gz", [])
    stats = parse_games(raw, tmp_path / "g.parquet")
    assert stats.written == 0
    assert stats.malformed_share == 0.0
    assert len(pd.read_parquet(tmp_path / "g.parquet")) == 0
