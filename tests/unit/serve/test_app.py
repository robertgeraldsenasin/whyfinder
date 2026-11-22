"""The REST API (FR-21): responses, exact explanations, limits and problem+json errors."""

from __future__ import annotations

import json
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from tests.unit.serve.conftest import ROOT
from whyfinder.serve.app import (
    MAX_BODY,
    PROBLEM,
    RateLimiter,
    create_app,
)
from whyfinder.serve.model import Filters, ServedModel

OPEN = {"explain": 10**9, "default": 10**9}


@pytest.fixture(scope="module")
def client(full: ServedModel) -> TestClient:
    return TestClient(create_app(full, git_sha="test-sha", limiter=RateLimiter(OPEN)))


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


def test_search_health_and_version(client: TestClient, full: ServedModel) -> None:
    hits = client.get("/search", params={"q": "portal"}).json()["items"]
    assert [h["title"] for h in hits][:1] == ["Portal 2"]
    is_problem(client.get("/search", params={"q": ""}), 422)
    assert client.get("/healthz").json() == {
        "status": "ok",
        "artifacts": "ok",
        "index": "ok",
        "llm": "off",
    }
    v = client.get("/version").json()
    assert v["git_sha"] == "test-sha"
    assert v["artifacts"] == full.hashes


def test_without_reviews_the_index_is_reported_missing(served: ServedModel) -> None:
    c = TestClient(create_app(served, limiter=RateLimiter(OPEN)))
    assert c.get("/healthz").json()["index"] == "not_built"
    is_problem(c.get("/reviews", params={"q": "co-op"}), 503)


def test_reviews_are_searched_across_the_catalogue_and_within_one_game(
    client: TestClient, full: ServedModel
) -> None:
    hits = client.get("/reviews", params={"q": "co-op with friends", "k": 5}).json()["items"]
    assert len(hits) == 5
    assert all(h["bm25_rank"] is not None or h["dense_rank"] is not None for h in hits)
    assert [h["score"] for h in hits] == sorted((h["score"] for h in hits), reverse=True)
    portal = client.get("/reviews", params={"q": "puzzles", "game_id": "620"}).json()["items"]
    assert portal
    assert {h["game_id"] for h in portal} == {"620"}
    assert {h["title"] for h in portal} == {"Portal 2"}
    assert client.get("/reviews", params={"q": "the a of"}).json()["items"] == []
    is_problem(client.get("/reviews", params={"q": "x", "game_id": "999999999"}), 404)
    is_problem(client.get("/reviews", params={"q": "x", "k": 0}), 422)


def test_explanations_quote_reviews_of_the_pick_verbatim(
    client: TestClient, full: ServedModel, liked: list[str]
) -> None:
    quoted = 0
    for item in client.post("/recommend", json={"liked_game_ids": liked}).json()["items"]:
        e = client.post("/explain", json={"liked_game_ids": liked, "game_id": item["game_id"]})
        body = e.json()
        assert body["checker"]["passed"], body["checker"]
        for claim in body["claims"]:
            for ev in claim["evidence"]:
                if ev["type"] != "review":
                    continue
                quoted += 1
                chunk = next(c for c in full.reviews.chunks if c.chunk_id == ev["chunk_id"])
                assert str(full.ids[chunk.game]) == item["game_id"]
                assert ev["quote"] == chunk.text
                assert ev["quote"] in claim["text"]
    assert quoted > 0


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


def test_the_committed_openapi_document_matches_the_code(client: TestClient) -> None:
    committed = json.loads((ROOT / "docs" / "openapi.json").read_text())
    assert client.get("/openapi.json").json() == committed, (
        "docs/openapi.json is out of date: run `uv run whyfinder serve openapi`"
    )


def test_a_body_that_is_not_json_is_a_bad_request(client: TestClient) -> None:
    for path in ("/recommend", "/explain"):
        r = client.post(path, content=b"\xff{", headers={"content-type": "application/json"})
        assert is_problem(r, 400)["title"] == "Bad request"


class Fake:
    """A stand-in model server: answers from a script, one answer per call."""

    model = "fake"

    def __init__(self, answers: list[str], *, down: bool = False) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.down = down

    @property
    def digest(self) -> str:
        if self.down:
            from whyfinder.rag.generate import LlmUnavailableError

            raise LlmUnavailableError("connection refused")
        return "sha256:fake"

    def complete(self, prompt: str, *, seed: int, schema: dict[str, Any]) -> str:
        self.prompts.append(prompt)
        if self.down:
            from whyfinder.rag.generate import LlmUnavailableError

            raise LlmUnavailableError("connection refused")
        return self.answers.pop(0)


def first_pick(c: TestClient, liked: list[str]) -> dict[str, Any]:
    item: dict[str, Any] = c.post("/recommend", json={"liked_game_ids": liked}).json()["items"][0]
    return item


def test_a_faithful_generation_is_served_as_is(full: ServedModel, liked: list[str]) -> None:
    base = TestClient(create_app(full, limiter=RateLimiter(OPEN)))
    pick = first_pick(base, liked)
    top = base.post("/explain", json={"liked_game_ids": liked, "game_id": pick["game_id"]}).json()
    a = top["attributions"][0]
    said = f"{a['title']} carries this pick ({round(a['share'] * 100)}%)."
    fake = Fake([json.dumps({"claims": [{"fact": "A1", "text": said}]})])
    c = TestClient(create_app(full, limiter=RateLimiter(OPEN), llm=fake))
    e = c.post("/explain", json={"liked_game_ids": liked, "game_id": pick["game_id"]}).json()
    assert [cl["text"] for cl in e["claims"]] == [said]
    assert e["checker"] == {"passed": True, "fallback_used": False, "reasons": []}
    assert len(fake.prompts) == 1
    assert pick["title"] in fake.prompts[0]
    assert c.get("/healthz").json()["llm"] == "ok"


def test_an_unfaithful_generation_is_retried_then_replaced(
    full: ServedModel, liked: list[str]
) -> None:
    pick = first_pick(TestClient(create_app(full, limiter=RateLimiter(OPEN))), liked)
    wrong = json.dumps({"claims": [{"fact": "A1", "text": "Dota 2 is why (90%)."}]})
    fake = Fake([wrong, "not json"])
    c = TestClient(create_app(full, limiter=RateLimiter(OPEN), llm=fake))
    e = c.post("/explain", json={"liked_game_ids": liked, "game_id": pick["game_id"]}).json()
    assert e["checker"]["passed"]
    assert e["checker"]["fallback_used"]
    assert any("matches no cited share" in r for r in e["checker"]["reasons"])
    assert any("claim schema" in r for r in e["checker"]["reasons"])
    assert "Your last answer was rejected" in fake.prompts[1]
    assert "is the biggest driver of this pick" in e["claims"][0]["text"]


def test_a_model_server_that_is_down_degrades_to_the_template(
    full: ServedModel, liked: list[str]
) -> None:
    c = TestClient(create_app(full, limiter=RateLimiter(OPEN), llm=Fake([], down=True)))
    pick = first_pick(c, liked)
    e = c.post("/explain", json={"liked_game_ids": liked, "game_id": pick["game_id"]}).json()
    assert e["checker"]["passed"]
    assert e["checker"]["fallback_used"]
    assert e["checker"]["reasons"][0].startswith("llm unavailable")
    health = c.get("/healthz").json()
    assert (health["status"], health["llm"]) == ("degraded", "down")


def test_counterfactual_evidence_round_trips_through_the_api_types() -> None:
    from whyfinder.rag import claims as rc
    from whyfinder.serve.app import to_api, to_rag

    claim = rc.Claim(
        "Without A and B it drops.",
        (
            rc.CounterfactualRef(("1", "2")),
            rc.AttributionRef("1", 0.5),
            rc.ReviewRef("c_1_0", "fun"),
        ),
    )
    assert to_rag(to_api(claim)) == claim
