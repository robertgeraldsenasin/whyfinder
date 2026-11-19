from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from tests.unit.eval.data import synthetic
from whyfinder.eval.explanations import CHECKS, _spearman, check
from whyfinder.eval.harness import build_models, eval_set, evaluate
from whyfinder.params import load_params


def small_params() -> dict[str, Any]:
    p = load_params()
    p["ials"].update({"factors": 4, "sweeps": 2})
    p["graph"]["top_m"] = 20
    p["blend"]["top_k_per_row"] = 20
    p["dpp"]["candidates"] = 15
    p["eval"]["explain"] = {"users": 25, "pool": 5, "deletion_draws": 3}
    return p


def served_fixture() -> tuple[Any, Any]:
    train, valid, games = synthetic()
    # Longer histories so the deletion test applies: give every user two more train games.
    extra = valid.assign(hours=5.0)
    es = eval_set(pd.concat([train, extra]), valid, item_cap=32, alpha=1.0, eps=1.0)
    _, _, served = build_models(es, games, small_params(), seed=1, only=("blend",))
    return es, served


def test_the_blend_is_additive_and_its_counterfactuals_are_valid() -> None:
    es, served = served_fixture()
    assert served is not None
    out = check(es, served, users=20, pool=5, draws=3, seed=2)
    assert out["users"] == 20
    assert set(out["per_user"]) == set(CHECKS)
    assert all(len(v) == 20 for v in out["per_user"].values())
    assert out["means"]["additivity"] == 1.0
    assert out["means"]["cf_validity"] == 1.0
    gaps = [g for g in out["per_user"]["minimality_gap"] if g is not None]
    assert all(g >= 0 for g in gaps)  # exact is the minimum among the pool, greedy never beats it
    assert out["pipeline_runs_mean"] > 0


def test_checks_are_part_of_the_report_when_configured() -> None:
    train, valid, games = synthetic()
    es = eval_set(train, valid, item_cap=32, alpha=1.0, eps=1.0, max_users=30)
    report = evaluate(es, games, small_params(), seed=1, only=("blend", "whyfinder"))
    assert report["explanations"]["users"] == 25
    assert report["explanations"]["means"]["additivity"] == 1.0


def test_spearman_by_hand() -> None:
    assert _spearman(np.array([1.0, 2.0, 3.0]), np.array([10.0, 20.0, 30.0])) == pytest.approx(1.0)
    assert _spearman(np.array([1.0, 2.0, 3.0]), np.array([3.0, 2.0, 1.0])) == pytest.approx(-1.0)
    assert _spearman(np.array([1.0, 1.0, 1.0]), np.array([1.0, 2.0, 3.0])) == 0.0


def test_bad_arguments_are_rejected() -> None:
    es, served = served_fixture()
    with pytest.raises(ValueError, match="positive"):
        check(es, served, users=0, pool=5, draws=3, seed=1)
