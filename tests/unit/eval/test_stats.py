from __future__ import annotations

import numpy as np
import pytest

from whyfinder.eval.stats import bootstrap_indices, holm, paired


def test_identical_models_give_zero_delta_and_pass_non_inferiority() -> None:
    x = np.random.default_rng(0).random(500)
    c = paired(x, x.copy(), margin=0.005, resamples=500, seed=1)
    assert c.delta == 0.0
    assert c.low == 0.0
    assert c.high == 0.0
    assert c.p_value == pytest.approx(1 / 501)


def test_a_known_shift_is_recovered() -> None:
    rng = np.random.default_rng(2)
    base = rng.random(4000)
    head = base + 0.02 + rng.normal(0, 0.05, 4000)
    c = paired(base, head, margin=0.0, resamples=2000, seed=3)
    se = float(np.std(head - base) / np.sqrt(4000))
    assert c.delta == pytest.approx(float(np.mean(head - base)))
    assert c.low < c.delta < c.high
    assert abs(c.delta - 0.02) < 4 * se
    assert c.high - c.low == pytest.approx(2 * 1.96 * se, rel=0.15)
    assert c.p_value < 0.01


def test_a_clear_regression_fails_non_inferiority() -> None:
    rng = np.random.default_rng(4)
    base = rng.random(3000)
    head = base - 0.05
    c = paired(base, head, margin=0.005, resamples=1000, seed=5)
    assert c.high < -0.005
    assert c.p_value > 0.5


def test_the_interval_is_reproducible_from_the_seed() -> None:
    rng = np.random.default_rng(6)
    a, b = rng.random(300), rng.random(300)
    assert paired(a, b, margin=0.01, resamples=300, seed=7) == paired(
        a, b, margin=0.01, resamples=300, seed=7
    )
    idx = bootstrap_indices(300, 300, 7)
    assert paired(a, b, margin=0.01, indices=idx) == paired(
        a, b, margin=0.01, resamples=300, seed=7
    )


def test_holm_steps_down_and_stops_at_the_first_failure() -> None:
    # m = 3: thresholds 0.05/3, 0.05/2, 0.05/1 for the sorted p-values.
    assert holm([0.01, 0.02, 0.04]) == [True, True, True]
    assert holm([0.02, 0.001, 0.04]) == [True, True, True]
    assert holm([0.001, 0.2, 0.01]) == [True, False, True]
    # 0.03 is the second smallest and exceeds 0.05/2, so it and everything after it fail.
    assert holm([0.01, 0.04, 0.03]) == [True, False, False]
    assert holm([]) == []


def test_bad_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="same length"):
        paired(np.zeros(3), np.zeros(4), margin=0.0)
    with pytest.raises(ValueError, match="margin"):
        paired(np.zeros(3), np.zeros(3), margin=-1.0)
    with pytest.raises(ValueError, match="level"):
        paired(np.zeros(3), np.zeros(3), margin=0.0, level=1.0)
    with pytest.raises(ValueError, match="alpha"):
        holm([0.1], alpha=0.0)
    with pytest.raises(ValueError, match="at least one"):
        bootstrap_indices(0, 10, 1)
