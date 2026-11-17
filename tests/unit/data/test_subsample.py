from __future__ import annotations

import pandas as pd
import pytest

from whyfinder.data.clean import hash_user
from whyfinder.data.subsample import in_subsample, subsample


def test_subsample_is_deterministic_and_close_to_the_fraction() -> None:
    users = pd.Series([hash_user(f"u{i}", "s") for i in range(4000)])
    mask = in_subsample(users, 0.05)
    assert mask.equals(in_subsample(users, 0.05))
    assert 0.03 < mask.mean() < 0.07
    assert in_subsample(users, 1.0).all()
    with pytest.raises(ValueError, match="fraction"):
        in_subsample(users, 0.0)
    tables = subsample({"t": pd.DataFrame({"user": users, "x": range(4000)})}, 0.05)
    assert len(tables["t"]) == int(mask.sum())
