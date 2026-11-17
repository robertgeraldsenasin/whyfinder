from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from whyfinder.data.features import build_features, confidence


def train() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "user": ["b", "a", "a", "c", "c", "c"],
            "game": [5, 5, 7, 5, 7, 9],
            "hours": [0.0, 1.0, 10.0, 0.0, 0.0, 3.0],
        }
    )


def test_confidence_is_one_without_hours_and_grows_slowly() -> None:
    values = confidence(np.array([0.0, 1.0, 100.0]), alpha=1.0, eps=1.0)
    assert values[0] == 1.0
    assert values[1] == pytest.approx(1 + np.log(2))
    assert np.all(np.diff(values) > 0)
    with pytest.raises(ValueError, match="alpha"):
        confidence(np.array([1.0]), alpha=1.0, eps=0.0)


def test_build_features_caps_items_by_count_then_id() -> None:
    f = build_features(train(), item_cap=2, alpha=1.0, eps=1.0)
    assert f.items["game"].tolist() == [5, 7]  # 9 has one interaction
    assert f.items["train_count"].tolist() == [3, 2]
    assert f.users["user"].tolist() == ["a", "b", "c"]
    dense = f.X.toarray()
    assert dense.shape == (3, 2)
    assert dense[0, 1] == pytest.approx(1 + np.log(11))
    assert dense[1, 1] == 0.0
    assert f.X.has_sorted_indices
    with pytest.raises(ValueError, match="item_cap"):
        build_features(train(), item_cap=0, alpha=1.0, eps=1.0)
