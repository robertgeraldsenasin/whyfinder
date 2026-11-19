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
