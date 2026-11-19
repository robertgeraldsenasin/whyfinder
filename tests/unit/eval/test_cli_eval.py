"""The eval, gate and results commands end to end on a tiny Parquet dataset."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.unit.eval.data import synthetic
from whyfinder.cli import app

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    train, valid, games = synthetic()
    d = tmp_path / "ci"
    d.mkdir()
    train.to_parquet(d / "train.parquet")
    valid.to_parquet(d / "valid.parquet")
    valid.to_parquet(d / "test.parquet")
    games.to_parquet(d / "games.parquet")
    return d


def small_params(tmp_path: Path) -> Path:
    text = (ROOT / "params.yaml").read_text()
    text = text.replace("sweeps: 15", "sweeps: 2").replace("factors: 64", "factors: 4")
    text = text.replace("top_m: 200", "top_m: 20").replace("candidates: 100", "candidates: 15")
    path = tmp_path / "params.yaml"
    path.write_text(text)
    return path


def test_eval_then_gate_then_results(
    data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    params = small_params(tmp_path)
    out = tmp_path / "head.json"
    run = CliRunner().invoke(
        app, ["eval", "--data", str(data_dir), "--out", str(out), "--params", str(params), "--gate"]
    )
    assert run.exit_code == 0, run.output
    assert "whyfinder" in run.output
    assert "users" in run.output
    report = json.loads(out.read_text())
    assert report["split"] == "valid"
    assert len(report["users"]) > 50

    gate_md = tmp_path / "gate.md"
    first = CliRunner().invoke(
        app, ["gate", "--head", str(out), "--out", str(gate_md), "--params", str(params)]
    )
    assert first.exit_code == 0
    assert "no baseline on main yet" in gate_md.read_text()
    same = CliRunner().invoke(
        app,
        [
            "gate",
            "--base",
            str(out),
            "--head",
            str(out),
            "--out",
            str(gate_md),
            "--params",
            str(params),
        ],
    )
    assert same.exit_code == 0
    assert "PASS" in gate_md.read_text()

    worse = json.loads(out.read_text())
    block = worse["models"]["whyfinder"]["per_user"]
    block["ndcg_at_10"] = [0.0 for _ in block["ndcg_at_10"]]
    (tmp_path / "worse.json").write_text(json.dumps(worse))
    failed = CliRunner().invoke(
        app,
        [
            "gate",
            "--base",
            str(out),
            "--head",
            str(tmp_path / "worse.json"),
            "--out",
            str(gate_md),
            "--params",
            str(params),
        ],
    )
    assert failed.exit_code == 1
    assert "FAIL" in gate_md.read_text()

    monkeypatch.setenv("WHYFINDER_RELEASE", "1")
    test_out = tmp_path / "test.json"
    sealed = CliRunner().invoke(
        app,
        [
            "eval",
            "--data",
            str(data_dir),
            "--split",
            "test",
            "--out",
            str(test_out),
            "--params",
            str(params),
            "--models",
            "popularity,ease",
        ],
    )
    assert sealed.exit_code == 0, sealed.output
    results = tmp_path / "results"
    written = CliRunner().invoke(
        app, ["results", "--report", str(test_out), "--out", str(results), "--params", str(params)]
    )
    assert written.exit_code == 0
    assert sorted(p.name for p in results.iterdir()) == ["ease.json", "popularity.json", "targets"]
    goals = json.loads((results / "targets" / "test.json").read_text())
    assert goals["split"] == "test"
    assert {g["id"] for g in goals["targets"]} >= {"ranking-ials", "diversity", "deletion"}
    assert "targets met" in written.output


def test_the_test_split_is_sealed_outside_release(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("WHYFINDER_RELEASE", raising=False)
    run = CliRunner().invoke(app, ["eval", "--data", str(data_dir), "--split", "test"])
    assert run.exit_code != 0
    assert "sealed" in run.output


def test_unknown_split_is_rejected(data_dir: Path) -> None:
    run = CliRunner().invoke(app, ["eval", "--data", str(data_dir), "--split", "train"])
    assert run.exit_code != 0
