"""The whole M0 pipeline, end to end, on the synthetic raw files, through the CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from whyfinder.cli import app

STAGES = ["parse", "clean", "kcore", "split", "features", "subsample", "stats"]


@pytest.fixture
def workdir(raw_dir: Path, params_file: Path) -> Path:
    root = raw_dir.parents[1]
    old = Path.cwd()
    os.chdir(root)
    yield root  # type: ignore[misc]
    os.chdir(old)


def run(*args: str) -> str:
    result = CliRunner().invoke(app, list(args))
    assert result.exit_code == 0, result.output
    return result.output


def test_parse_clean_kcore(workdir: Path) -> None:
    for stage in ("parse", "clean", "kcore"):
        run("data", stage)
    processed = workdir / "data" / "processed"
    clean = json.loads((processed / "clean_stats.json").read_text())
    core = json.loads((processed / "kcore_stats.json").read_text())
    assert clean["dropped_unknown_game"] == 1
    assert clean["dropped_no_user"] == 1
    assert clean["duplicates_removed"] >= 1
    assert 0.9 < clean["date_coverage"] < 1.0
    assert core["k"] == 3
    assert core["rows_out"] <= clean["rows_out"]
    games = pd.read_parquet(processed / "games.parquet")
    assert len(games) == clean["catalogue_games"] == 15


def test_split_and_features(workdir: Path) -> None:
    for stage in ("parse", "clean", "kcore", "split", "features"):
        run("data", stage)
    split = json.loads((workdir / "data" / "split.json").read_text())
    assert split["method"] == "global_time"
    assert split["t1"] < split["t2"]
    processed = workdir / "data" / "processed"
    train = pd.read_parquet(processed / "train.parquet")
    test = pd.read_parquet(processed / "test.parquet")
    assert train["date"].max() < test["date"].min()
    features = json.loads((processed / "features_stats.json").read_text())
    assert features["items"] <= 12
    assert 0 < features["train_rows_covered"] <= 1
