from __future__ import annotations

from typing import Any

from tests.unit.eval.data import synthetic
from whyfinder.eval.harness import eval_set
from whyfinder.eval.tune import tune
from whyfinder.params import load_params


def small_params() -> dict[str, Any]:
    p = load_params()
    p["ials"].update({"factors": 4, "sweeps": 2})
    p["graph"]["top_m"] = 20
    p["blend"]["top_k_per_row"] = 20
    p["dpp"]["candidates"] = 15
    p["tune"].update(
        {
            "ease_lambda": [5.0, 50.0],
            "knn_shrinkage": [0.0, 10.0],
            "ials_reg": [0.1, 1.0],
            "ials_alpha": [1.0],
            "blend_beta": [0.0, 0.5, 1.0],
            "dpp_theta": [1.0, 4.0],
        }
    )
    return p


def test_every_grid_is_searched_and_the_best_values_come_from_it() -> None:
    train, valid, games = synthetic()
    es = eval_set(train, valid, item_cap=32, alpha=1.0, eps=1.0)
    p = small_params()
    report = tune(es, games, p, seed=3)
    grids = report["grids"]
    assert [r["lambda"] for r in grids["ease"]] == [5.0, 50.0]
    assert len(grids["ials"]) == 2
    assert [r["beta"] for r in grids["blend"]] == [0.0, 0.5, 1.0]
    best = report["best"]
    assert best["ease.lambda"] == max(grids["ease"], key=lambda r: r["ndcg_at_10"])["lambda"]
    assert best["blend.beta"] in {0.0, 0.5, 1.0}
    assert best["dpp.theta"] in {1.0, 4.0}
    for row in grids["dpp"]:
        assert 0.0 <= row["ild_at_10"] <= 1.0
    chosen = next(r for r in grids["dpp"] if r["theta"] == best["dpp.theta"])
    assert chosen["within_budget"] or not any(r["within_budget"] for r in grids["dpp"])
