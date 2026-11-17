# 12 · API

FastAPI; schemas are Pydantic models; the OpenAPI document is generated and committed at
`docs/openapi.json` (CI fails if it drifts). Errors use `application/problem+json` (RFC 9457).

| Endpoint | Request | Response |
| --- | --- | --- |
| `POST /recommend` | `liked_game_ids` (3–50) **or** `query` (string); `k` (1–20, default 10); `filters` {`tags`, `max_price`, `year_min`, `year_max`}; `diversity` (bool, default true) | `items`: [{`game_id`, `title`, `score`, `rank`, `kept_for_variety`, `top_reason`}]; `unresolved_terms`; `model_version` |
| `POST /explain` | `liked_game_ids` or `query`; `game_id` | `attributions`: [{`game_id`, `title`, `contribution`, `share`, `ease_part`, `ppr_part`}]; `counterfactual` {`removed_game_ids`, `guarantee`: `irreducible` \| `exact_min`}; `paths`; `kept_for_variety`; `claims` (verified); `checker` {`passed`, `fallback_used`, `reasons`} |
| `GET /search?q=` | title prefix or words | up to 10 catalogue matches (for the query bar) |
| `GET /healthz` | — | status of artifacts, index and LLM (LLM down ⇒ `degraded`, template explanations still served) |
| `GET /version` | — | git SHA, model version, data version, artifact hashes |

**Limits:** 30 requests/min per IP on `/explain`, 120 on others; request body ≤ 16 KB.

**Example**

```http
POST /explain
{"liked_game_ids": ["1145360", "588650", "504230"], "game_id": "367520"}
```

```json
{
  "attributions": [
    {"game_id": "588650", "title": "Dead Cells", "contribution": 0.214, "share": 0.42, "ease_part": 0.121, "ppr_part": 0.093}
  ],
  "counterfactual": {"removed_game_ids": ["588650"], "guarantee": "irreducible"},
  "paths": [{"via": "tag", "label": "Metroidvania", "rarity": 0.81}],
  "kept_for_variety": false,
  "claims": [{"text": "Dead Cells is the biggest driver of this pick (42%).", "evidence": [{"type": "attribution", "game_id": "588650", "share": 0.42}]}],
  "checker": {"passed": true, "fallback_used": false, "reasons": []}
}
```

(Values are illustrative.)
