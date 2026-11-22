"""Browsers may call the API from the demo's origins, and only those (the demo's live mode)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from whyfinder.serve.app import ORIGINS, RateLimiter, create_app, origins
from whyfinder.serve.model import ServedModel

PAGES = "https://robertgeraldsenasin.github.io"
PREFLIGHT = {
    "access-control-request-method": "POST",
    "access-control-request-headers": "content-type",
}


@pytest.fixture(scope="module")
def browser(served: ServedModel) -> TestClient:
    limits = RateLimiter({"explain": 1, "default": 1})
    return TestClient(create_app(served, git_sha="t", limiter=limits, cors=ORIGINS))


def test_the_demo_origin_passes_the_preflight(browser: TestClient) -> None:
    r = browser.options("/explain", headers={"origin": PAGES, **PREFLIGHT})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == PAGES
    assert "POST" in r.headers["access-control-allow-methods"]
    assert "access-control-allow-private-network" not in r.headers


def test_another_origin_is_refused(browser: TestClient) -> None:
    r = browser.options(
        "/explain",
        headers={
            "origin": "https://elsewhere.example",
            "access-control-request-private-network": "true",
            **PREFLIGHT,
        },
    )
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers


def test_a_private_network_preflight_is_answered_for_the_demo(browser: TestClient) -> None:
    headers = {"origin": PAGES, "access-control-request-private-network": "true", **PREFLIGHT}
    r = browser.options("/explain", headers=headers)
    assert r.status_code == 200
    assert r.headers["access-control-allow-private-network"] == "true"


def test_preflights_do_not_spend_the_rate_limit_and_answers_carry_the_origin(
    browser: TestClient,
) -> None:
    for _ in range(3):
        assert (
            browser.options("/version", headers={"origin": PAGES, **PREFLIGHT}).status_code == 200
        )
    r = browser.get("/version", headers={"origin": PAGES})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == PAGES
    limited = browser.get("/version", headers={"origin": PAGES})
    assert limited.status_code == 429
    assert limited.headers["access-control-allow-origin"] == PAGES


def test_without_origins_nothing_cross_origin_is_allowed(served: ServedModel) -> None:
    plain = TestClient(create_app(served, git_sha="t"))
    r = plain.options("/explain", headers={"origin": PAGES, **PREFLIGHT})
    assert r.status_code == 405
    assert "access-control-allow-origin" not in r.headers


def test_origins_come_from_the_environment_or_default_to_the_demo() -> None:
    assert origins({}) == ORIGINS
    assert PAGES in ORIGINS
    assert origins({"WHYFINDER_CORS_ORIGINS": " https://a.example/ , http://localhost:9000,"}) == (
        "https://a.example",
        "http://localhost:9000",
    )
    assert origins({"WHYFINDER_CORS_ORIGINS": ""}) == ()
