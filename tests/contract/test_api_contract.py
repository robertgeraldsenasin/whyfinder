"""Contract tests (FR-21): Schemathesis generates requests from the committed OpenAPI document's
source, the running app, and checks every response against it (status codes, content types,
response schemas, no server errors, valid data accepted and invalid data rejected).
"""

from __future__ import annotations

import pytest

schemathesis = pytest.importorskip("schemathesis")
pytest.importorskip("fastapi")

from hypothesis import HealthCheck, settings  # noqa: E402

from tests.serving import served  # noqa: E402
from whyfinder.serve.app import RateLimiter, create_app  # noqa: E402

APP = create_app(
    served(with_reviews=True),
    git_sha="contract",
    limiter=RateLimiter({"explain": 10**9, "default": 10**9}),
)
schema = schemathesis.openapi.from_asgi("/openapi.json", APP)


@schema.parametrize()
@settings(max_examples=40, deadline=None, suppress_health_check=list(HealthCheck))
def test_the_api_keeps_its_contract(case: schemathesis.Case) -> None:
    case.call_and_validate()
