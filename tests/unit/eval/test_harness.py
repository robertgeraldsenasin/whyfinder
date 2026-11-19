from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tests.unit.eval.data import synthetic
from whyfinder.eval.harness import MODELS, eval_set, evaluate, top_n
from whyfinder.params import load_params


def params() -> dict:
    p = load_params()
    p["ials"].update({"factors": 4, "sweeps": 3})
    p["graph"]["top_m"] = 20
    p["blend"]["top_k_per_row"] = 20
    p["dpp"]["candidates"] = 15
    return p


def test_eval_set_keeps_users_with_history_and_held_out_games_inside_the_cap() -> None:
    train, valid, _ = synthetic()
    valid = pd.concat(
        [
            valid,
            pd.DataFrame([("ffffffff", 100, 1.0), ("00000000", 999, 1.0)], columns=valid.columns),
        ]
    )
    es = eval_set(train, valid, item_cap=32, alpha=1.0, eps=1.0)
    assert "ffffffff" not in es.users  # no train history
    assert es.users == sorted(es.users)
    assert len(es.users) == len(es.relevant) == len(es.rows)
    first = es.users[0]
    cols = {
        int(np.flatnonzero(es.game_ids == g)[0])
        for g in valid.loc[valid["user"] == first, "game"]
        if g in set(es.game_ids)
    }
    assert es.relevant[0] == cols
    assert len(eval_set(train, valid, item_cap=32, alpha=1.0, eps=1.0, max_users=7).users) == 7


def test_top_n_drops_owned_games_and_breaks_ties_by_game_id() -> None:
    scores = np.array([0.5, 0.9, 0.5, 0.9, 0.1])
    ids = np.array([50, 40, 30, 41, 10])
    assert top_n(scores, set(), ids, 3) == [1, 3, 2]
    assert top_n(scores, {1}, ids, 3) == [3, 2, 0]
    assert top_n(scores, {0, 1, 2, 3, 4}, ids, 3) == []


def test_every_model_is_scored_on_the_same_users() -> None:
    train, valid, games = synthetic()
    es = eval_set(train, valid, item_cap=32, alpha=1.0, eps=1.0)
    report = evaluate(es, games, params(), seed=1)
    assert list(report["models"]) == list(MODELS)
    for name, block in report["models"].items():
        for metric, values in block["per_user"].items():
            assert len(values) == len(es.users), (name, metric)
        assert 0.0 <= block["means"]["ndcg_at_10"] <= 1.0
        assert 0.0 < block["coverage_at_10"] <= 1.0
    means = {n: b["means"]["ndcg_at_10"] for n, b in report["models"].items()}
    # The clusters are easy: co-play models must beat popularity here.
    assert means["ease"] > means["popularity"]
    assert means["itemknn"] > means["popularity"]
    assert report["models"]["ials"]["info"]["losses"] == sorted(
        report["models"]["ials"]["info"]["losses"], reverse=True
    )


def test_evaluate_runs_a_subset_and_rejects_unknown_models() -> None:
    train, valid, games = synthetic()
    es = eval_set(train, valid, item_cap=32, alpha=1.0, eps=1.0, max_users=20)
    report = evaluate(es, games, params(), seed=1, only=("popularity", "ease"))
    assert list(report["models"]) == ["popularity", "ease"]
    with pytest.raises(ValueError, match="unknown model"):
        evaluate(es, games, params(), seed=1, only=("magic",))


def test_peak_memory_counts_the_build_and_leaves_tracing_as_it_was() -> None:
    import tracemalloc

    from whyfinder.eval.harness import peak_memory

    out, peak = peak_memory(lambda: np.ones((512, 512)))
    assert out.shape == (512, 512)
    assert peak >= 512 * 512 * 8
    assert not tracemalloc.is_tracing()
    tracemalloc.start()
    try:
        _, inner = peak_memory(lambda: np.zeros(1000))
        assert inner >= 8000
        assert tracemalloc.is_tracing()
    finally:
        tracemalloc.stop()


def test_peak_memory_stops_tracing_when_the_build_fails() -> None:
    import tracemalloc

    from whyfinder.eval.harness import peak_memory

    def boom() -> np.ndarray:
        raise ValueError("no")

    with pytest.raises(ValueError, match="no"):
        peak_memory(boom)
    assert not tracemalloc.is_tracing()
