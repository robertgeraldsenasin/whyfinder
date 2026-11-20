# 12 · API

FastAPI; schemas are Pydantic models; the OpenAPI document is generated and committed at
`docs/openapi.json` (a test fails if it drifts; regenerate with `uv run whyfinder serve openapi`).
Errors use `application/problem+json` (RFC 9457). The API serves the demo-slice model (ADR-0019), so
its picks and reasons equal the live demo's for the same games.

| Endpoint | Request | Response |
| --- | --- | --- |
| `POST /recommend` | `liked_game_ids` (1–50 Steam app IDs as strings) and/or `query` (≤ 300 chars); `k` (1–20, default 10); `filters` {`tags`, `max_price`, `year_min`, `year_max`}; `diversity` (bool, default true; false gives the relevance-only top k) | `items`: [{`game_id`, `title`, `score`, `rank`, `kept_for_variety`, `top_reason`}]; `liked_game_ids` (the ones used); `unknown_game_ids`; `unresolved_terms`; `model_version` |
| `POST /explain` | the same taste fields; `game_id` | `score`, `rank` (null if not picked); `attributions`: [{`game_id`, `title`, `contribution`, `share`, `ease_part`, `ppr_part`}]; `counterfactual` {`removed_game_ids`, `guarantee`: `irreducible` \| `exact_min` \| `not_in_picks`, `pipeline_runs`}; `paths` [{`via`, `label`, `from_game_id`, `weight`}]; `kept_for_variety`; `claims` (verified); `checker` {`passed`, `fallback_used`, `reasons`} |
| `GET /search?q=` | 1–100 characters | up to 10 catalogue titles: those starting with `q`, then those containing it |
| `GET /reviews?q=&game_id=&k=` | 1–200 characters; optional game; `k` 1–20 (default 5) | review quotes ranked by RRF over BM25 and LSA vectors in HNSW, each with `chunk_id`, `game_id`, `title`, `text`, `hours`, `year`, `score`, `bm25_rank`, `dense_rank`; 503 if the server has no review index |
| `GET /healthz` | — | `status`, `artifacts`, `index` (`ok` once the review index is built, `not_built` without reviews), `llm` (`off` with no model, `ok`, or `down`, which makes `status` `degraded` while template explanations are still served) |
| `GET /version` | — | git SHA, model version, data version, SHA-256 of the slice and params |

A `query` is read like the demo's description box (the two parsers share their test cases in
`web/src/lib/__fixtures__/queries.json`): titles become liked games, tags, prices and years become
filters, and anything else comes back in `unresolved_terms`.

**Status codes:** 400 when a body is not valid JSON; 404 when no liked game (from IDs or the query) is in the catalogue, or the game to
explain is not; 409 when the game to explain is one of the liked games; 413 for bodies over 16 KB;
422 when the body does not match the schema (the problem lists each error); 429 over the rate limit.
Inputs are strict: `"2010"` is not a year and `1` is not `true`, though `2010.0` is an integer, as
in JSON Schema.

**Limits:** 30 requests/min per client IP on `/explain`, 120 on the rest (fixed one-minute windows,
per process); request body ≤ 16 KB.

**Claims and the checker.** With no model configured, the claims are template sentences
(`fallback_used: true`): one or two from the attributions and up to two quoting a review of the pick
that mentions an aspect it shares with your top game (06_RAG). With `WHYFINDER_LLM_MODEL` (and
`WHYFINDER_LLM_URL`, default `http://127.0.0.1:11434`) set, an Ollama model writes them from the same
facts (it cites numbered facts; code attaches the evidence in the claim schema,
`docs/spec/claim.schema.json`); the checker verifies every claim, the
model gets one retry with the checker's reasons, and the template sentences replace it after that.
`checker.reasons` then lists why the model's answers were rejected. The checker confirms each cited
game is among the top five with its computed share, any percentage is within a point of it, each
quote is a verbatim span (≤ 25 words) of a chunk of the pick's reviews, a counterfactual claim cites
exactly the computed set, and no sentence names a game outside the pick and the history.

**Example** (real output, numbers rounded)

```http
POST /explain
{"liked_game_ids": ["620", "49520", "500"], "game_id": "440"}
```

```json
{
  "game_id": "440", "title": "Team Fortress 2", "score": 2.072, "rank": 1,
  "attributions": [
    {"game_id": "620", "title": "Portal 2", "contribution": 0.874, "share": 0.422, "ease_part": 0.510, "ppr_part": 0.363},
    {"game_id": "49520", "title": "Borderlands 2", "contribution": 0.732, "share": 0.353, "ease_part": 0.433, "ppr_part": 0.299},
    {"game_id": "500", "title": "Left 4 Dead", "contribution": 0.467, "share": 0.225, "ease_part": 0.042, "ppr_part": 0.425}
  ],
  "counterfactual": {"removed_game_ids": ["620", "49520", "500"], "guarantee": "irreducible", "pipeline_runs": 6},
  "paths": [
    {"via": "tag", "label": "Comedy", "from_game_id": "620", "weight": 1.835},
    {"via": "tag", "label": "Online Co-Op", "from_game_id": "620", "weight": 1.649}
  ],
  "kept_for_variety": false,
  "claims": [
    {"text": "Portal 2 is the biggest driver of this pick (42%).", "evidence": [{"type": "attribution", "game_id": "620", "share": 0.422}]},
    {"text": "Borderlands 2 adds 35%.", "evidence": [{"type": "attribution", "game_id": "49520", "share": 0.353}]}
  ],
  "checker": {"passed": true, "fallback_used": true, "reasons": []},
  "model_version": "blend-slice-1"
}
```

**Running it**

```bash
uv sync --group serve
uv run whyfinder serve run                     # http://127.0.0.1:8000/docs (reviews index ~20 s)
docker build -f docker/Dockerfile.api -t whyfinder-api .
docker run -p 8000:8000 whyfinder-api          # or ghcr.io/robertgeraldsenasin/whyfinder-api
```

**Tests:** `tests/unit/serve/` (every endpoint, failure paths, limits, the checker, exactness and the
counterfactual against the pipeline) and `tests/contract/test_api_contract.py` (Schemathesis against
the running app: status codes, content types, response schemas, valid data accepted, invalid data
rejected).
