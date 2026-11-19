"""One served model per test process, shared by the API unit and contract tests (the review index
takes about 20 s to build)."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from whyfinder.serve.model import ServedModel

ROOT = Path(__file__).resolve().parents[1]
SLICE = ROOT / "web" / "public" / "data" / "demo-slice.json"
REVIEWS = ROOT / "web" / "public" / "data" / "reviews.json"
PARAMS = ROOT / "params.yaml"


@cache
def served(with_reviews: bool) -> ServedModel:
    return ServedModel.load(SLICE, PARAMS, REVIEWS if with_reviews else None)
