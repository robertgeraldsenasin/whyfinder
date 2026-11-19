from __future__ import annotations

import numpy as np
import pytest

from whyfinder.eval.results import REPORTED, summarize


def test_summary_has_means_and_intervals_per_model() -> None:
    rng = np.random.default_rng(1)
    per_user = {m: rng.random(400).tolist() for m in (*REPORTED, "arp_at_10")}
    report = {
        "users": [str(k) for k in range(400)],
        "models": {"ease": {"per_user": per_user, "coverage_at_10": 0.31}},
    }
    (row,) = summarize(report, "test", resamples=500, seed=2)
    assert row["model"] == "ease"
    assert row["split"] == "test"
    assert row["users"] == 400
    for name in REPORTED:
        m = row["metrics"][name]
        assert m["lo"] <= m["mean"] <= m["hi"]
        assert m["mean"] == pytest.approx(float(np.mean(per_user[name])), abs=1e-6)
    assert row["metrics"]["coverage_at_10"] == {"mean": 0.31, "lo": 0.31, "hi": 0.31}


def test_an_empty_report_is_rejected() -> None:
    with pytest.raises(ValueError, match="no users"):
        summarize({"users": [], "models": {}}, "test", resamples=10, seed=1)


def _report(n: int, *, explain: bool = True) -> dict[str, object]:
    rng = np.random.default_rng(3)
    base = rng.random(n) * 0.1

    def block(shift: float, ild: float) -> dict[str, object]:
        return {
            "per_user": {
                "ndcg_at_10": (base + shift).tolist(),
                "recall_at_20": (base * 2 + shift).tolist(),
                "mrr": base.tolist(),
                "ild_at_10": np.full(n, ild).tolist(),
            },
            "coverage_at_10": 0.3,
        }

    report: dict[str, object] = {
        "split": "test",
        "users": [str(k) for k in range(n)],
        "models": {
            "popularity": block(0.0, 0.70),
            "ials": block(0.01, 0.80),
            "blend": block(0.05, 0.80),
            "whyfinder": block(0.049, 0.84),
        },
    }
    if explain:
        report["explanations"] = {
            "means": {"additivity": 1.0, "cf_validity": 1.0, "deletion": 0.97}
        }
    return report


def test_targets_are_met_when_the_evidence_is_clear() -> None:
    from whyfinder.eval.results import targets

    out = targets(_report(500), resamples=500, seed=1)
    assert out["users"] == 500
    by_id = {row["id"]: row for row in out["targets"]}
    assert set(by_id) == {
        "ranking-ials",
        "ranking-popularity-ndcg-at-10",
        "ranking-popularity-recall-at-20",
        "diversity",
        "additivity",
        "cf-validity",
        "deletion",
    }
    assert all(row["met"] is True for row in out["targets"]), out
    assert "20.0% of the headroom" in by_id["diversity"]["detail"]


def test_targets_report_misses_and_missing_evidence() -> None:
    from whyfinder.eval.results import targets

    report = _report(300, explain=False)
    models = report["models"]
    assert isinstance(models, dict)
    models["whyfinder"] = models["popularity"]  # no better than popularity, no extra variety
    del models["ials"]
    by_id = {row["id"]: row for row in targets(report, resamples=300, seed=1)["targets"]}
    assert by_id["ranking-ials"]["met"] is None
    assert by_id["ranking-popularity-ndcg-at-10"]["met"] is False
    assert by_id["diversity"]["met"] is False
    assert by_id["deletion"]["met"] is None


def test_targets_need_users() -> None:
    from whyfinder.eval.results import targets

    with pytest.raises(ValueError, match="no users"):
        targets({"users": [], "models": {}}, resamples=10, seed=1)
