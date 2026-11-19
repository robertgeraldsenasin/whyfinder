"""One served model for every API test: the committed demo slice and params.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest

from whyfinder.serve.model import ServedModel

ROOT = Path(__file__).resolve().parents[3]
SLICE = ROOT / "web" / "public" / "data" / "demo-slice.json"
PARAMS = ROOT / "params.yaml"


@pytest.fixture(scope="session")
def served() -> ServedModel:
    return ServedModel.load(SLICE, PARAMS)


@pytest.fixture(scope="session")
def by_title(served: ServedModel) -> dict[str, int]:
    return {served.title(i): i for i in range(len(served.ids))}
