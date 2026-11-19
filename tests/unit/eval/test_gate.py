from __future__ import annotations

import copy

import numpy as np
import pytest

from whyfinder.eval.gate import MARKER, GateError, compare

MARGINS = {"ndcg_at_10": 0.005, "recall_at_20": 0.005, "ild_at_10": 0.01}


def report(shift: float = 0.0, n: int = 600, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    per_user = {
        "ndcg_at_10": (rng.random(n) * 0.3 + shift).clip(0, 1).tolist(),
        "recall_at_20": (rng.random(n) * 0.4 + shift).clip(0, 1).tolist(),
        "mrr": rng.random(n).tolist(),
        "ild_at_10": (rng.random(n) * 0.5 + 0.3).tolist(),
        "arp_at_10": rng.random(n).tolist(),
    }
    means = {k: float(np.mean(v)) for k, v in per_user.items()}
    block = {"per_user": per_user, "means": means, "coverage_at_10": 0.2, "build_seconds": 1.0}
    return {"users": [f"u{k}" for k in range(n)], "n_items": 100, "models": {"whyfinder": block}}


def test_without_a_baseline_the_gate_passes_and_says_why() -> None:
    v = compare(None, report(), margins=MARGINS, resamples=200, seed=1)
    assert v.passed
    assert v.markdown.startswith(MARKER)
    assert "no baseline on main yet" in v.markdown


def test_an_unchanged_model_passes() -> None:
    base = report()
    v = compare(base, copy.deepcopy(base), margins=MARGINS, resamples=300, seed=1)
    assert v.passed
    assert "PASS" in v.markdown
    assert "| NDCG@10 |" in v.markdown


def test_a_clear_regression_fails() -> None:
    base = report()
    head = copy.deepcopy(base)
    head["models"]["whyfinder"]["per_user"]["ndcg_at_10"] = [
        x - 0.05 for x in base["models"]["whyfinder"]["per_user"]["ndcg_at_10"]
    ]
    v = compare(base, head, margins=MARGINS, resamples=300, seed=1)
    assert not v.passed
    assert "FAIL" in v.markdown
    assert "non-inferior ✗" in v.markdown


def test_superiority_needs_a_real_gain() -> None:
    base = report()
    v = compare(base, copy.deepcopy(base), margins=MARGINS, resamples=300, seed=1, superiority=True)
    assert not v.passed


def test_reports_on_different_users_cannot_be_compared() -> None:
    with pytest.raises(GateError, match="different users"):
        compare(report(n=10), report(n=11), margins=MARGINS, resamples=50, seed=1)
    broken = report()
    del broken["models"]["whyfinder"]
    with pytest.raises(GateError, match="no per-user metrics"):
        compare(report(), broken, margins=MARGINS, resamples=50, seed=1)


def with_explanations(
    r: dict, *, valid: float = 1.0, deletion_shift: float = 0.0, seed: int = 0
) -> dict:
    rng = np.random.default_rng(seed)
    n = 200
    per_user = {
        "additivity": [1.0] * n,
        "cf_validity": [1.0 if k < valid * n else 0.0 for k in range(n)],
        "deletion": [float(x < 0.9 + deletion_shift) for x in rng.random(n)],
        "minimality_gap": [None if k % 10 == 0 else float(rng.integers(0, 2)) for k in range(n)],
        "sanity_spearman": rng.normal(0, 0.2, n).tolist(),
    }
    means = {m: float(np.mean([v for v in vals if v is not None])) for m, vals in per_user.items()}
    out = copy.deepcopy(r)
    out["explanations"] = {"users": n, "means": means, "per_user": per_user}
    return out


EXPLAIN = {"deletion": 0.01, "minimality_gap": 0.1}


def test_explanation_checks_are_compared_and_gated() -> None:
    base = with_explanations(report())
    v = compare(
        base, copy.deepcopy(base), margins=MARGINS, resamples=300, seed=1, explain_margins=EXPLAIN
    )
    assert v.passed
    assert "Counterfactual validity" in v.markdown
    assert "Deletion test" in v.markdown


def test_an_invalid_counterfactual_fails_the_gate_even_without_a_baseline() -> None:
    head = with_explanations(report(), valid=0.9)
    assert not compare(None, head, margins=MARGINS, resamples=100, seed=1).passed
    base = with_explanations(report())
    v = compare(base, head, margins=MARGINS, resamples=100, seed=1, explain_margins=EXPLAIN)
    assert not v.passed
    assert "100% ✗" in v.markdown


def test_a_worse_deletion_test_fails() -> None:
    base = with_explanations(report())
    head = with_explanations(report(), deletion_shift=-0.3)
    v = compare(base, head, margins=MARGINS, resamples=300, seed=1, explain_margins=EXPLAIN)
    assert not v.passed
