# 10 · Testing

Each layer is tested against an independent source of truth: a reference library, a brute-force
computation, a mathematical identity, or a fixture with a known answer.

| Level | Proves | Tools | Examples |
| --- | --- | --- | --- |
| Unit | Each function does what its docstring says, failure paths included | pytest | Empty history raises `EmptyHistoryError`; unknown game ID → 422 at the API |
| Property | Invariants hold for random inputs | Hypothesis | Attributions sum to the score; B_jj = 0; PPR mass ≤ 1; DPP picks are distinct; scoring never mutates inputs |
| Oracle | Hand-written code agrees with a reference | pytest + numpy / implicit / hnswlib / rank-bm25 | EASE vs dense inverse (1e-8); PPR push vs power iteration (ε·deg); HNSW recall ≥ 0.95 |
| Golden | Small known cases never change silently | snapshot files in `tests/golden/` | 6-user, 8-game toy: B, Π, blend scores, top 3, attributions, counterfactual |
| Data contract | Inputs have the agreed shape | Pandera | unique (user, game); time split monotonic |
| Statistical | Bootstrap and gates behave as designed | pytest + synthetic metric arrays | identical models pass; NDCG cut by 10% fails; Holm adjusts p-values correctly |
| RAG | The checker catches what it should | adversarial fixtures | fabricated quote, wrong %, unlisted game, wrong counterfactual → rejected |
| API contract | API matches its committed OpenAPI | Schemathesis, httpx | all endpoints, valid and invalid inputs |
| End-to-end | Demo works on the production build | Playwright + axe | pick 3 games → 10 picks with reasons; 0 violations |
| Load | Latency target holds | Locust | p95 < 150 ms at 20 rps, at release |

## Rules

- Every new module ships with tests, failure paths included (Definition of done).
- No network in unit tests; fixtures live in `tests/fixtures/` and are small (< 1 MB each).
- Seeds are explicit in every test that uses randomness.
- Coverage gate: ≥ 85% lines on `core`, `graph`, `rerank`, `explain`.
