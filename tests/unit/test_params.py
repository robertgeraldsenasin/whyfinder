"""params.yaml accessor."""

from __future__ import annotations

from pathlib import Path

import pytest

from whyfinder.params import ParamError, load_params, param


def test_params_accessor(params_file: Path) -> None:
    p = load_params(params_file)
    assert param(p, "data.kcore", int) == 3
    assert param(p, "data.confidence.alpha", float) == 1.0
    assert param(p, "split.valid_quantile", float) == 0.6
    with pytest.raises(ParamError, match="missing"):
        param(p, "data.nope", int)
    with pytest.raises(ParamError, match="must be str"):
        param(p, "data.kcore", str)


def test_params_file_must_be_a_mapping(tmp_path: Path) -> None:
    path = tmp_path / "p.yaml"
    path.write_text("- a\n- b\n")
    with pytest.raises(ParamError, match="mapping"):
        load_params(path)
