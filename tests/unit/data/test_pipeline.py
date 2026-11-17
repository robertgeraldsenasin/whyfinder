"""The whole M0 pipeline, end to end, on the synthetic raw files, through the CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest
import scipy.sparse as sp
from typer.testing import CliRunner

from whyfinder.cli import app
from whyfinder.data.fetch import sha256_file, write_checksums
from whyfinder.params import load_params, param

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


def test_pipeline_end_to_end(workdir: Path) -> None:
    for stage in STAGES:
        run("data", stage)
    stats = json.loads((workdir / "data" / "stats.json").read_text())
    assert set(stats) == {"parse", "clean", "kcore", "split", "features", "ci_subsample"}
    assert stats["parse"]["reviews"]["malformed"] == 1
    assert stats["parse"]["games"]["written"] == 15
    assert stats["clean"]["dropped_unknown_game"] == 1
    assert stats["clean"]["duplicates_removed"] >= 1
    assert 0.9 < stats["clean"]["date_coverage"] < 1.0
    assert stats["kcore"]["k"] == 3
    assert stats["split"]["method"] == "global_time"
    split = json.loads((workdir / "data" / "split.json").read_text())
    assert split == stats["split"]
    processed = workdir / "data" / "processed"
    train = pd.read_parquet(processed / "train.parquet")
    test = pd.read_parquet(processed / "test.parquet")
    assert train["date"].max() < test["date"].min()
    X = sp.load_npz(processed / "X_train.npz")
    assert X.shape == (stats["features"]["users"], stats["features"]["items"])
    assert stats["features"]["items"] <= 12
    manifest = json.loads((workdir / "data" / "ci" / "manifest.json").read_text())
    assert manifest == stats["ci_subsample"]
    assert 0 < manifest["rows"]["train"] < len(train)


def test_parse_with_workers_matches(workdir: Path) -> None:
    out = run("data", "parse", "--workers", "2")
    assert "malformed" in out


def test_fetch_verifies_existing_files(workdir: Path) -> None:
    raw = workdir / "data" / "raw"
    write_checksums(
        workdir / "data" / "checksums.txt",
        {p.name: sha256_file(p) for p in raw.glob("*.gz")},
    )
    out = run("data", "fetch")
    assert out.count("kept") == 2


def test_fetch_rejects_unknown_source(workdir: Path) -> None:
    result = CliRunner().invoke(app, ["data", "fetch", "--only", "nope"])
    assert result.exit_code != 0
    assert "unknown source" in result.output


def test_repository_params_have_every_m0_key() -> None:
    p = load_params(Path(__file__).resolve().parents[3] / "params.yaml")
    for key, kind in [
        ("data.kcore", int),
        ("data.item_cap", int),
        ("data.user_salt", str),
        ("data.hours_clip_quantile", float),
        ("data.parse_tolerance", float),
        ("data.ci_user_fraction", float),
        ("split.valid_quantile", float),
        ("split.test_quantile", float),
        ("split.cold_max_train_items", int),
        ("split.max_missing_date", float),
    ]:
        param(p, key, kind)
