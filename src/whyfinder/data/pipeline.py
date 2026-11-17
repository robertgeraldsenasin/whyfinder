"""The data stages as file-to-file functions; `dvc.yaml` runs them through the CLI.

Layout:

    data/raw/              downloaded files (never committed)
    data/interim/          parsed tables
    data/processed/        cleaned, k-cored, split tables and X_train
    data/ci/               the pinned CI subsample (published as release asset data-ci-v1)
    data/checksums.txt     SHA-256 of every raw file          (committed)
    data/split.json        cut-offs, counts and table hashes  (committed)
    data/stats.json        every count the README may quote    (committed)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from whyfinder.data.parse import parse_games, parse_reviews
from whyfinder.data.sources import SOURCES

SPLITS = ("train", "valid", "test", "cold")


def write_json(path: Path, payload: object) -> None:
    """Deterministic JSON: sorted keys, two-space indent, trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stage_parse(raw: Path, interim: Path, *, workers: int, tolerance: float) -> dict[str, Any]:
    reviews = parse_reviews(
        raw / SOURCES["reviews"].filename,
        interim / "reviews.parquet",
        interim / "review_text.parquet",
        workers=workers,
        tolerance=tolerance,
    )
    games = parse_games(raw / SOURCES["games"].filename, interim / "games.parquet")
    stats = {
        name: {"lines": s.lines, "malformed": s.malformed, "written": s.written}
        for name, s in (("reviews", reviews), ("games", games))
    }
    write_json(interim / "parse_stats.json", stats)
    return stats
