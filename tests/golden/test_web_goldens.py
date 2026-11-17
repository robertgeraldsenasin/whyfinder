"""The browser engine's goldens must come from the current Python core (ADR-0015).

Rebuilds the model on the committed demo slice and compares with the committed goldens and model
file. If this fails after a change to the core, run `uv run whyfinder export model` and commit the
result; Vitest then checks the TypeScript engine against the new goldens.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from whyfinder.export.model import build_model, goldens, model_file, model_params
from whyfinder.params import load_params

ROOT = Path(__file__).resolve().parents[2]
SLICE = ROOT / "web" / "public" / "data" / "demo-slice.json"
MODEL = ROOT / "web" / "public" / "data" / "model.json"
GOLDENS = ROOT / "web" / "src" / "engine" / "__goldens__" / "goldens.json"


def same(a: Any, b: Any, path: str = "$") -> None:
    """Equal structure; floats within 1e-9 relative (BLAS builds differ in the last bits)."""
    if isinstance(a, float) or isinstance(b, float):
        assert isinstance(a, int | float), path
        assert isinstance(b, int | float), path
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12), f"{path}: {a} != {b}"
    elif isinstance(a, dict):
        assert isinstance(b, dict), path
        assert a.keys() == b.keys(), path
        for k in a:
            same(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert isinstance(b, list), path
        assert len(a) == len(b), f"{path}: length {len(a)} != {len(b)}"
        for k, (x, y) in enumerate(zip(a, b, strict=True)):
            same(x, y, f"{path}[{k}]")
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"


@pytest.fixture(scope="module")
def model():  # type: ignore[no-untyped-def]
    return build_model(
        json.loads(SLICE.read_text()), model_params(load_params(ROOT / "params.yaml"))
    )


def test_goldens_match_the_python_core(model) -> None:  # type: ignore[no-untyped-def]
    committed = json.loads(GOLDENS.read_text())
    same(json.loads(json.dumps(goldens(model))), committed)
    assert len(committed["cases"]) >= 4


def test_model_file_matches(model) -> None:  # type: ignore[no-untyped-def]
    committed = json.loads(MODEL.read_text())
    fresh = json.loads(json.dumps(model_file(model)))
    for timing in ("easeSeconds", "piSeconds"):
        committed["build"].pop(timing)
        fresh["build"].pop(timing)
    same(fresh, committed)
    assert 0.0 <= committed["build"]["piTruncationLoss"]["max"] < 1.0
