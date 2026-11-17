from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from whyfinder.core.blend import blend, scale_constant
from whyfinder.explain.attributions import attributions, total_in_history_order
from whyfinder.explain.counterfactual import exact, greedy
from whyfinder.explain.paths import related_by
from whyfinder.graph.build import GameInfo, Weights, build_graph
from whyfinder.rerank.dpp import tfidf_vectors
from whyfinder.rerank.pipeline import recommend


def world(n: int = 60, seed: int = 4) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    B = rng.normal(0, 1, (n, n)) * (rng.random((n, n)) < 0.3)
    Pi = rng.random((n, n)) * (rng.random((n, n)) < 0.2)
    np.fill_diagonal(B, 0.0)
    np.fill_diagonal(Pi, 0.0)
    c_B, c_Pi = scale_constant(B), scale_constant(Pi)
    M = blend(B, Pi, 0.5, c_B, c_Pi)
    tags = ["a", "b", "c", "d", "e", "f"]
    feats = [list(rng.choice(tags, size=2, replace=False)) for _ in range(n)]
    return {
        "B": B,
        "Pi": Pi,
        "M": M,
        "c_B": c_B,
        "c_Pi": c_Pi,
        "vectors": tfidf_vectors(feats),
        "ids": list(range(500, 500 + n)),
    }


@settings(max_examples=40, deadline=None)
@given(st.integers(0, 5000), st.integers(1, 8))
def test_attributions_sum_to_the_score(seed: int, size: int) -> None:
    w = world()
    rng = np.random.default_rng(seed)
    history = [(int(j), float(rng.uniform(1, 5))) for j in rng.choice(60, size, replace=False)]
    rec = recommend(history, w["M"], vectors=w["vectors"], game_ids=w["ids"], k=5)  # type: ignore[arg-type]
    for pick in rec.picks:
        parts = attributions(
            history,
            pick,
            w["M"],
            w["B"],
            w["Pi"],
            beta=0.5,  # type: ignore[arg-type]
            c_B=w["c_B"],
            c_Pi=w["c_Pi"],
            game_ids=w["ids"],
        )  # type: ignore[arg-type]
        assert total_in_history_order(history, pick, w["M"]) == rec.scores[pick]  # type: ignore[arg-type]
        assert abs(sum(p.total for p in parts) - rec.scores[pick]) < 1e-9
        for p in parts:
            assert abs(p.ease + p.ppr - p.total) < 1e-12
        assert [p.total for p in parts] == sorted((p.total for p in parts), reverse=True)


def pipeline_for(w: dict[str, object]):  # type: ignore[no-untyped-def]
    def run(history: list[tuple[int, float]]) -> list[int]:
        return recommend(history, w["M"], vectors=w["vectors"], game_ids=w["ids"], k=5).picks  # type: ignore[arg-type]

    return run


@pytest.mark.parametrize("seed", range(6))
def test_counterfactuals_are_valid_irreducible_and_near_minimal(seed: int) -> None:
    w = world(seed=seed)
    rng = np.random.default_rng(seed)
    history = [(int(j), float(rng.uniform(1, 5))) for j in rng.choice(60, 6, replace=False)]
    run = pipeline_for(w)
    picks = run(history)
    for pick in picks[:3]:
        parts = attributions(
            history,
            pick,
            w["M"],
            w["B"],
            w["Pi"],
            beta=0.5,  # type: ignore[arg-type]
            c_B=w["c_B"],
            c_Pi=w["c_Pi"],
            game_ids=w["ids"],
        )  # type: ignore[arg-type]
        order = [p.game for p in parts]
        cf = greedy(run, history, pick, order)
        removed = set(cf.removed)
        rest = [(j, x) for j, x in history if j not in removed]
        assert not rest or pick not in run(rest)  # valid: the full pipeline drops the pick
        for j in cf.removed:  # irreducible: putting any game back keeps the pick out
            back = [(g, x) for g, x in history if g not in removed - {j}]
            if len(cf.removed) > 1:
                assert pick in run(back)
        best = exact(run, history, pick, order, max_size=3, pool=20)
        if best is not None:
            assert len(best.removed) <= len(cf.removed)
            rest = [(j, x) for j, x in history if j not in set(best.removed)]
            assert pick not in run(rest)
        assert cf.runs >= 1
        assert cf.trail[0][0] == "remove"


def test_exact_returns_none_when_no_small_set_works() -> None:
    def always(history: list[tuple[int, float]]) -> list[int]:
        return [99]

    assert exact(always, [(1, 1.0), (2, 1.0), (3, 1.0), (4, 1.0)], 99, [1, 2, 3, 4]) is None
    cf = greedy(always, [(1, 1.0), (2, 1.0)], 99, [1, 2])
    assert cf.removed == [1, 2]  # removing everything is the only way: no history, no picks


def test_related_by_finds_shared_tags_and_co_play() -> None:
    games = [
        GameInfo(["Metroidvania", "Action"], "Team Cherry", None),
        GameInfo(["Metroidvania", "Souls-like"], "Motion Twin", None),
        GameInfo(["Action"], "Team Cherry", None),
        GameInfo(["Puzzle"], None, None),
    ]
    S = np.zeros((4, 4))
    S[0, 1] = S[1, 0] = 0.9
    graph = build_graph(games, S, weights=Weights(), tags_per_game=5, coplay_per_game=2)
    paths = related_by(graph, 0, 1)
    assert [p.kind for p in paths] == ["tag", "co-play"]  # rare tag idf ln(1+4/2) ≈ 1.10 > 0.9
    assert paths[0].via is not None
    assert graph.names[paths[0].via] == "Metroidvania"
    dev = related_by(graph, 0, 2, limit=5)
    assert {p.kind for p in dev} == {"tag", "developer"}
    assert related_by(graph, 0, 3) == []
