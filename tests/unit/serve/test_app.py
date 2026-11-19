"""The REST API (FR-21): responses, exact explanations, limits and problem+json errors."""

from __future__ import annotations

import json
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from tests.unit.serve.conftest import ROOT
from whyfinder.serve import schemas as s
from whyfinder.serve.app import (
    MAX_BODY,
    PROBLEM,
    RateLimiter,
    check_claims,
    claims_for,
    create_app,
)
from whyfinder.serve.model import Filters, ServedModel

OPEN = {"explain": 10**9, "default": 10**9}


@pytest.fixture(scope="module")
def client(served: ServedModel) -> TestClient:
    return TestClient(create_app(served, git_sha="test-sha", limiter=RateLimiter(OPEN)))


@pytest.fixture(scope="module")
def liked(by_title: dict[str, int], served: ServedModel) -> list[str]:
    return [str(served.ids[by_title[t]]) for t in ("Portal 2", "Borderlands 2", "Left 4 Dead")]


def is_problem(r: Any, status: int) -> dict[str, Any]:
    assert r.status_code == status, r.text
    assert r.headers["content-type"].startswith(PROBLEM)
    body: dict[str, Any] = r.json()
    assert body["status"] == status
    assert {"type", "title", "detail"} <= set(body)
    return body


def test_recommend_returns_ranked_picks_with_their_top_reason(
    client: TestClient, liked: list[str]
) -> None:
    r = client.post("/recommend", json={"liked_game_ids": [*liked, "999999999"], "k": 5})
    assert r.status_code == 200
    body = r.json()
    assert [i["rank"] for i in body["items"]] == [1, 2, 3, 4, 5]
    assert body["liked_game_ids"] == liked
    assert body["unknown_game_ids"] == ["999999999"]
    assert body["model_version"] == "blend-slice-1"
    picked = {i["game_id"] for i in body["items"]}
    assert not picked & set(liked)
    for item in body["items"]:
        assert item["top_reason"]["game_id"] in liked
        assert 0 < item["top_reason"]["share"] <= 1


def test_recommend_matches_the_pipeline_with_and_without_diversity(
    client: TestClient, served: ServedModel, liked: list[str]
) -> None:
    history, _ = served.history([int(g) for g in liked])
    for diversity in (True, False):
        r = client.post("/recommend", json={"liked_game_ids": liked, "diversity": diversity})
        rec = served.run(history, k=10, filters=Filters(), diversity=diversity)
        assert [i["game_id"] for i in r.json()["items"]] == [str(served.ids[p]) for p in rec.picks]


def test_a_description_sets_anchors_and_filters_that_every_pick_keeps(
    client: TestClient, served: ServedModel
) -> None:
    r = client.post(
        "/recommend", json={"query": "like Portal 2, co-op, under $15, since 2010, blorp"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["unresolved_terms"] == ["blorp"]
    assert body["items"]
    f = Filters(("Co-op",), 15.0, 2010, None)
    for item in body["items"]:
        assert f.passes(served.games[served.index[int(item["game_id"])]])


def test_filters_in_the_body_are_kept_and_an_impossible_one_gives_no_picks(
    client: TestClient, liked: list[str]
) -> None:
    r = client.post(
        "/recommend",
        json={"liked_game_ids": liked, "filters": {"year_min": 2020, "year_max": 2010}},
    )
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_explain_is_exact_and_its_counterfactual_holds(
    client: TestClient, liked: list[str]
) -> None:
    first = client.post("/recommend", json={"liked_game_ids": liked}).json()["items"][0]
    r = client.post("/explain", json={"liked_game_ids": liked, "game_id": first["game_id"]})
    assert r.status_code == 200
    e = r.json()
    assert e["rank"] == 1
    assert sum(a["contribution"] for a in e["attributions"]) == pytest.approx(e["score"], abs=1e-9)
    for a in e["attributions"]:
        assert a["ease_part"] + a["ppr_part"] == pytest.approx(a["contribution"], abs=1e-9)
    assert sum(abs(a["share"]) for a in e["attributions"]) == pytest.approx(1.0)
    cf = e["counterfactual"]
    assert cf["guarantee"] == "irreducible"
    assert cf["removed_game_ids"]
    rest = [g for g in liked if g not in cf["removed_game_ids"]]
    if rest:
        again = client.post("/recommend", json={"liked_game_ids": rest}).json()["items"]
        assert first["game_id"] not in {i["game_id"] for i in again}
    assert e["checker"] == {"passed": True, "fallback_used": True, "reasons": []}
    assert e["claims"]
    assert e["claims"][0]["evidence"][0]["game_id"] == e["attributions"][0]["game_id"]


def test_explaining_a_game_that_is_not_picked(
    client: TestClient, served: ServedModel, liked: list[str]
) -> None:
    picks = {
        i["game_id"]
        for i in client.post("/recommend", json={"liked_game_ids": liked}).json()["items"]
    }
    other = next(str(g) for g in served.ids if str(g) not in picks and str(g) not in liked)
    e = client.post("/explain", json={"liked_game_ids": liked, "game_id": other}).json()
    assert e["rank"] is None
    assert e["counterfactual"] == {
        "removed_game_ids": [],
        "guarantee": "not_in_picks",
        "pipeline_runs": 0,
    }


def test_explain_refuses_unknown_and_liked_games(client: TestClient, liked: list[str]) -> None:
    is_problem(client.post("/explain", json={"liked_game_ids": liked, "game_id": "999999999"}), 404)
    is_problem(client.post("/explain", json={"liked_game_ids": liked, "game_id": liked[0]}), 409)


def test_a_taste_the_catalogue_does_not_know_is_not_found(client: TestClient) -> None:
    is_problem(client.post("/recommend", json={"liked_game_ids": ["999999999"]}), 404)
    is_problem(client.post("/recommend", json={"query": "zzzyzzx"}), 404)
    is_problem(client.post("/recommend", json={"query": None}), 404)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"liked_game_ids": []},
        {"liked_game_ids": ["12a"]},
        {"liked_game_ids": ["١٢٣"]},
        {"liked_game_ids": ["620"], "k": 0},
        {"liked_game_ids": ["620"], "k": "3"},
        {"liked_game_ids": ["620"], "k": 2.5},
        {"liked_game_ids": ["620"], "diversity": 1},
        {"liked_game_ids": ["620"], "filters": {"year_min": "2010"}},
        {"liked_game_ids": ["620"], "filters": {"max_price": -1}},
        {"liked_game_ids": ["620"], "surprise": True},
        {"query": ""},
    ],
)
def test_invalid_bodies_are_rejected_with_their_errors(
    client: TestClient, body: dict[str, Any]
) -> None:
    problem = is_problem(client.post("/recommend", json=body), 422)
    assert problem["errors"]


def test_integral_floats_count_as_integers(client: TestClient, liked: list[str]) -> None:
    r = client.post("/recommend", json={"liked_game_ids": liked, "k": 3.0})
    assert r.status_code == 200
    assert len(r.json()["items"]) == 3


def test_search_health_and_version(client: TestClient, served: ServedModel) -> None:
    hits = client.get("/search", params={"q": "portal"}).json()["items"]
    assert [h["title"] for h in hits][:1] == ["Portal 2"]
    is_problem(client.get("/search", params={"q": ""}), 422)
    assert client.get("/healthz").json() == {
        "status": "ok",
        "artifacts": "ok",
        "index": "not_built",
        "llm": "off",
    }
    v = client.get("/version").json()
    assert v["git_sha"] == "test-sha"
    assert v["artifacts"] == served.hashes


def test_bodies_over_the_limit_are_refused_before_parsing(client: TestClient) -> None:
    big = b'{"liked_game_ids": ["620"], "query": "' + b"a" * MAX_BODY + b'"}'
    is_problem(
        client.post("/recommend", content=big, headers={"content-type": "application/json"}), 413
    )


def test_unknown_paths_and_methods_are_problems_too(client: TestClient) -> None:
    is_problem(client.get("/nowhere"), 404)
    r = client.put("/recommend")
    is_problem(r, 405)
    assert r.headers["allow"] == "POST"


def test_the_rate_limit_is_per_client_and_per_minute(served: ServedModel, liked: list[str]) -> None:
    now = [0.0]
    limiter = RateLimiter({"explain": 1, "default": 2}, clock=lambda: now[0])
    c = TestClient(create_app(served, limiter=limiter))
    assert c.get("/healthz").status_code == 200
    assert c.get("/healthz").status_code == 200
    r = is_problem(c.get("/healthz"), 429)
    assert "2 requests a minute" in r["detail"]
    body = {"liked_game_ids": liked, "game_id": "999999999"}
    assert c.post("/explain", json=body).status_code == 404
    is_problem(c.post("/explain", json=body), 429)
    assert limiter.allow("someone else", "default")
    now[0] = 61.0
    assert c.get("/healthz").status_code == 200


def test_the_checker_rejects_claims_that_do_not_match_the_attributions() -> None:
    rows = [
        s.Attribution(
            game_id="1", title="A", contribution=0.6, share=0.6, ease_part=0.4, ppr_part=0.2
        ),
        s.Attribution(
            game_id="2", title="B", contribution=0.4, share=0.4, ease_part=0.1, ppr_part=0.3
        ),
    ]
    claims = claims_for(rows)
    assert [c.text for c in claims] == [
        "A is the biggest driver of this pick (60%).",
        "B adds 40%.",
    ]
    assert check_claims(claims, rows).passed
    wrong_share = [
        s.Claim(
            text="A drives 60%.", evidence=[s.Evidence(type="attribution", game_id="1", share=0.5)]
        )
    ]
    outsider = [
        s.Claim(
            text="C drives it.", evidence=[s.Evidence(type="attribution", game_id="9", share=0.6)]
        )
    ]
    unstated = [
        s.Claim(
            text="A matters.", evidence=[s.Evidence(type="attribution", game_id="1", share=0.6)]
        )
    ]
    bare = [s.Claim(text="Trust me.", evidence=[])]
    for bad in (wrong_share, outsider, unstated, bare):
        checked = check_claims(bad, rows)
        assert not checked.passed
        assert checked.reasons


def test_a_small_second_reason_is_left_out() -> None:
    rows = [
        s.Attribution(
            game_id="1", title="A", contribution=0.95, share=0.95, ease_part=0.5, ppr_part=0.45
        ),
        s.Attribution(
            game_id="2", title="B", contribution=0.05, share=0.05, ease_part=0.0, ppr_part=0.05
        ),
    ]
    assert len(claims_for(rows)) == 1
    assert claims_for([]) == []


def test_the_committed_openapi_document_matches_the_code(client: TestClient) -> None:
    committed = json.loads((ROOT / "docs" / "openapi.json").read_text())
    assert client.get("/openapi.json").json() == committed, (
        "docs/openapi.json is out of date: run `uv run whyfinder serve openapi`"
    )
