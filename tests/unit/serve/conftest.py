"""The served models for the API tests: the committed demo slice, reviews and params.yaml."""

from __future__ import annotations

import pytest

from tests import serving
from tests.serving import PARAMS, REVIEWS, ROOT, SLICE
from whyfinder.serve.model import ServedModel

__all__ = ["PARAMS", "REVIEWS", "ROOT", "SLICE"]


@pytest.fixture(scope="session")
def served() -> ServedModel:
    """The model alone, without the review index."""
    return serving.served(with_reviews=False)


@pytest.fixture(scope="session")
def full() -> ServedModel:
    """The model with the review index, as `whyfinder serve run` and the image start it."""
    return serving.served(with_reviews=True)


@pytest.fixture(scope="session")
def by_title(served: ServedModel) -> dict[str, int]:
    return {served.title(i): i for i in range(len(served.ids))}
