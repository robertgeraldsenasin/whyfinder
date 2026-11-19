"""iALS explanations (FR-11, issue #25): Sherman–Morrison downdates against a fresh solve."""

from __future__ import annotations

import numpy as np
import pytest

from whyfinder.core.ials import fold_in
from whyfinder.explain.ials import (
    attributions,
    counterfactual,
    fold,
    pipeline,
    top,
    without,
    without_all,
)

REG, ALPHA, K = 0.1, 5.0, 10


def setup(
    seed: int, n: int = 80, f: int = 8, size: int = 12
) -> tuple[np.ndarray, list[tuple[int, float]]]:
    rng = np.random.default_rng(seed)
    Y = rng.normal(scale=0.4, size=(n, f))
    games = rng.choice(n, size=size, replace=False)
    history = [(int(j), float(w)) for j, w in zip(games, rng.uniform(0.0, 3.0, size), strict=True)]
    return Y, history


def rest_of(history: list[tuple[int, float]], removed: set[int]) -> list[tuple[int, float]]:
    return [(j, w) for j, w in history if j not in removed]


@pytest.mark.parametrize("seed", range(8))
def test_a_downdate_equals_a_fresh_solve(seed: int) -> None:
    Y, history = setup(seed)
    user = fold(history, Y, reg=REG, alpha=ALPHA)
    assert np.allclose(user.factor, fold_in(history, Y, reg=REG, alpha=ALPHA), atol=1e-10)
    removed: set[int] = set()
    for j, _ in history[:6]:
        user = without(user, j, Y)
        removed.add(j)
        rest = rest_of(history, removed)
        oracle = fold(rest, Y, reg=REG, alpha=ALPHA)
        assert np.max(np.abs(user.factor - fold_in(rest, Y, reg=REG, alpha=ALPHA))) < 1e-8
        assert np.max(np.abs(user.inverse - oracle.inverse)) < 1e-8
        assert np.allclose(user.inverse, user.inverse.T, atol=1e-12)


def test_removing_everything_leaves_the_prior() -> None:
    Y, history = setup(3)
    empty = without_all(fold(history, Y, reg=REG, alpha=ALPHA), [j for j, _ in history], Y)
    assert np.allclose(empty.b, 0.0, atol=1e-12)
    assert np.allclose(empty.factor, 0.0, atol=1e-12)
    assert empty.confidence == {}


def test_a_zero_weight_game_only_changes_b() -> None:
    Y, history = setup(4)
    history = [(history[0][0], 0.0), *history[1:]]
    user = fold(history, Y, reg=REG, alpha=ALPHA)
    after = without(user, history[0][0], Y)
    assert np.array_equal(after.inverse, user.inverse)
    assert np.allclose(after.b, user.b - Y[history[0][0]])


@pytest.mark.parametrize("seed", range(5))
def test_attributions_sum_to_the_score_exactly(seed: int) -> None:
    Y, history = setup(seed)
    user = fold(history, Y, reg=REG, alpha=ALPHA)
    ids = np.arange(Y.shape[0]) + 1000
    for pick in range(0, Y.shape[0], 7):
        parts = attributions(user, Y, pick, ids)
        assert {j for j, _ in parts} == {j for j, _ in history}
        assert sum(v for _, v in parts) == pytest.approx(float(Y[pick] @ user.factor), abs=1e-9)
        values = [v for _, v in parts]
        assert values == sorted(values, reverse=True)


def test_the_pipeline_matches_fresh_solves_on_any_part_of_the_history() -> None:
    Y, history = setup(5)
    ids = np.arange(Y.shape[0])
    run = pipeline(fold(history, Y, reg=REG, alpha=ALPHA), Y, ids, K)
    rng = np.random.default_rng(0)
    for _ in range(10):
        keep = rng.random(len(history)) < 0.6
        rest = [h for h, kept in zip(history, keep, strict=True) if kept]
        owned = {j for j, _ in rest}
        oracle = top(Y @ fold_in(rest, Y, reg=REG, alpha=ALPHA), owned, ids, K)
        assert run(rest) == oracle


@pytest.mark.parametrize("seed", range(6))
def test_counterfactuals_are_valid_and_irreducible_by_fresh_solves(seed: int) -> None:
    Y, history = setup(seed, size=6)
    ids = np.arange(Y.shape[0])
    user = fold(history, Y, reg=REG, alpha=ALPHA)
    picks = top(Y @ user.factor, {j for j, _ in history}, ids, K)

    def shown(rest: list[tuple[int, float]]) -> list[int]:
        return top(Y @ fold_in(rest, Y, reg=REG, alpha=ALPHA), {j for j, _ in rest}, ids, K)

    for pick in picks[:3]:
        cf = counterfactual(user, Y, ids, pick, K)
        assert cf.removed
        rest = rest_of(history, set(cf.removed))
        assert not rest or pick not in shown(rest)
        for j in cf.removed:
            back = rest_of(history, set(cf.removed) - {j})
            assert pick in shown(back)


def test_a_pick_outside_the_top_k_needs_no_removal() -> None:
    Y, history = setup(6)
    ids = np.arange(Y.shape[0])
    user = fold(history, Y, reg=REG, alpha=ALPHA)
    order = top(Y @ user.factor, {j for j, _ in history}, ids, Y.shape[0])
    cf = counterfactual(user, Y, ids, order[-1], K)
    assert cf.removed == []


def test_inputs_are_not_mutated() -> None:
    Y, history = setup(7)
    Y0 = Y.copy()
    user = fold(history, Y, reg=REG, alpha=ALPHA)
    inverse, b, conf = user.inverse.copy(), user.b.copy(), dict(user.confidence)
    without(user, history[0][0], Y)
    attributions(user, Y, 0, np.arange(Y.shape[0]))
    assert np.array_equal(Y, Y0)
    assert np.array_equal(user.inverse, inverse)
    assert np.array_equal(user.b, b)
    assert user.confidence == conf


def test_failure_paths() -> None:
    Y, history = setup(8)
    user = fold(history, Y, reg=REG, alpha=ALPHA)
    outside = next(j for j in range(Y.shape[0]) if j not in user.confidence)
    with pytest.raises(KeyError):
        without(user, outside, Y)
    with pytest.raises(ValueError, match="twice"):
        fold([*history, history[0]], Y, reg=REG, alpha=ALPHA)
    with pytest.raises(KeyError):
        pipeline(user, Y, np.arange(Y.shape[0]), K)([(outside, 1.0)])
    empty = fold([], Y, reg=REG, alpha=ALPHA)
    assert np.array_equal(empty.factor, np.zeros(Y.shape[1]))
    assert attributions(empty, Y, 0, np.arange(Y.shape[0])) == []
