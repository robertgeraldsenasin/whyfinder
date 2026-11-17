"""Shared fixtures: small synthetic raw files in the UCSD format (Python-literal dicts per line)."""

from __future__ import annotations

import gzip
import random
from datetime import date, timedelta
from pathlib import Path

import pytest

GAMES = list(range(10, 25))  # 15 games
UNKNOWN_GAME = 999


def _review_lines(seed: int = 7) -> list[str]:
    rng = random.Random(seed)
    lines: list[str] = []
    start = date(2015, 1, 1)
    for u in range(60):
        for game in rng.sample(GAMES, rng.randint(6, 12)):
            day = start + timedelta(days=rng.randint(0, 4 * 365))
            record: dict[str, object] = {
                "username": f"player {u}",
                "product_id": str(game),
                "date": day.isoformat() if rng.random() > 0.03 else "not a date",
                "text": f"Review by {u} of {game}. Loved the combat.",
                "early_access": False,
                "page": 1,
            }
            if rng.random() > 0.05:
                record["hours"] = round(rng.lognormvariate(2.5, 1.2), 1)
            lines.append(repr(record))
    # edge cases: a duplicate with more hours, an unknown game, a missing user, a malformed line
    lines.append(
        repr(
            {
                "username": "player 0",
                "product_id": "10",
                "hours": 9999.0,
                "date": "2015-06-01",
                "text": "again",
            }
        )
    )
    lines.append(
        repr(
            {
                "username": "player 1",
                "product_id": str(UNKNOWN_GAME),
                "hours": 1.0,
                "date": "2016-01-01",
                "text": "?",
            }
        )
    )
    lines.append(repr({"product_id": "11", "hours": 2.0, "date": "2016-01-01", "text": "anon"}))
    lines.append("{'username': 'broken', 'product_id': ")
    return lines


def _game_lines() -> list[str]:
    tags = ["Roguelike", "Action", "Indie", "Co-op", "Puzzle", "RPG", "Strategy", "Platformer"]
    lines = []
    for i, game in enumerate(GAMES):
        lines.append(
            repr(
                {
                    "id": str(game),
                    "app_name": f"Game {game}",
                    "title": f"Game {game}",
                    "developer": f"Studio {game % 4}",
                    "publisher": f"Publisher {game % 3}",
                    "genres": ["Action", "Indie"],
                    "tags": [tags[i % 8], tags[(i + 3) % 8], "Indie"],
                    "specs": ["Single-player"],
                    "price": "Free To Play" if game == 12 else 9.99 + i,
                    "release_date": f"{2010 + i % 9}-03-0{1 + i % 8}",
                    "early_access": False,
                    "sentiment": "Very Positive",
                    "metascore": 80 if i % 2 else "NA",
                }
            )
        )
    lines.append(repr({"app_name": "No id", "title": "No id"}))
    lines.append(repr({"id": "10", "title": "Duplicate of 10"}))
    return lines


def write_gz(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    """data/raw with steam_reviews.json.gz and steam_games.json.gz."""
    raw = tmp_path / "data" / "raw"
    write_gz(raw / "steam_reviews.json.gz", _review_lines())
    write_gz(raw / "steam_games.json.gz", _game_lines())
    return raw


PARAMS_YAML = """seed: 1
data:
  kcore: 3
  item_cap: 12
  ci_user_fraction: 0.5
  confidence: {alpha: 1.0, eps: 1.0}
  user_salt: test-salt
  hours_clip_quantile: 0.99
  parse_tolerance: 0.01
split:
  valid_quantile: 0.6
  test_quantile: 0.8
  cold_max_train_items: 2
  max_missing_date: 0.10
"""


@pytest.fixture
def params_file(tmp_path: Path) -> Path:
    path = tmp_path / "params.yaml"
    path.write_text(PARAMS_YAML, encoding="utf-8")
    return path
