# 02 · Requirements

Every requirement has an ID, a priority and an acceptance criterion that a test or a CI job checks.
Issues and PRs cite these IDs (`FR-07`), so every change traces back to a story.

## Functional requirements

| ID | Requirement | Pri. | Acceptance criterion | Story | Milestone |
| --- | --- | --- | --- | --- | --- |
| FR-01 | Fetch the raw Steam files by script; never commit them | Must | `whyfinder data fetch` reproduces the recorded SHA-256 of every file | US-10 | M0 |
| FR-02 | Build the interaction matrix: confidence from hours played; k-core filter | Must | Data contract passes: schema, unique (user, game), hours ≥ 0, k-core holds | US-01 | M0 |
| FR-03 | Split by time into train, validation, test | Must | No test interaction predates the train cut-off; split hashes recorded | US-09 | M0 |
| FR-04 | Baselines: popularity, item-kNN (cosine with shrinkage) | Must | Both run end to end and appear in every report | US-09 | M1 |
| FR-05 | EASE^R item-item matrix, hand-written | Must | Closed form matches a dense reference on a 300-item fixture to 1e-8; diagonal is 0 | US-01 | M1 |
| FR-06 | Heterogeneous game graph (games, tags, developers, publishers, co-play edges) | Must | Graph contract: no dangling edges, weights > 0, every game reachable from ≥ 1 tag or co-play edge | US-01 | M1 |
| FR-07 | Personalized PageRank per game by forward push, kept as a sparse item-item matrix (top M per row) | Must | Matches power iteration on a 2,000-node fixture within the push tolerance ε; truncation loss reported | US-01 | M1 |
| FR-08 | Glass-box blend M = β·B/c_B + (1−β)·Π/c_Π, scored as s_u = x_u M | Must | β, c_B, c_Π recorded per run; scoring is a sparse vector-matrix product | US-01 | M1 |
| FR-09 | iALS rival (Cholesky and conjugate-gradient solvers) | Must | Loss falls every sweep; NDCG@10 within 2% of the `implicit` library at equal settings | US-09 | M1 |
| FR-10 | Exact attributions: contribution of each history game to each pick | Must | Contributions sum to the blend score within 1e-9 | US-02 | M2 |
| FR-11 | Exact counterfactuals for the blend; greedy + Sherman–Morrison for iALS | Must | 100% of sets remove the pick when the full pipeline (incl. DPP) is re-run; exact minimal for size ≤ 3 | US-03 | M2 |
| FR-12 | DPP re-ranking (greedy MAP, incremental Cholesky) over the top 100 candidates | Should | Matches a brute-force log-det argmax on 12-candidate fixtures; picks kept for variety are flagged | US-05 | M2 |
| FR-13 | Path explanations from the graph ("same developer", "shares the rare tag …") labelled "related by" | Should | Every shown path exists in the graph | US-02 | M2 |
| FR-14 | Review corpus: per-game sample, chunked, BM25 index (hand-written) | Must | BM25 scores match a reference implementation on a fixture | US-04 | M3 |
| FR-15 | Dense retrieval on a hand-written HNSW index; reciprocal rank fusion with BM25 | Must | HNSW recall@10 ≥ 0.95 vs exact search; benchmarked against hnswlib | US-04 | M3 |
| FR-16 | Grounded generation: claims in a JSON schema, each citing an attribution or a review span | Must | Output validates against `claim.schema.json` | US-04 | M3 |
| FR-17 | Claim checker + template fallback | Must | Rejects absent attributions, non-verbatim quotes, wrong percentages, unlisted game names | US-04 | M3 |
| FR-18 | Natural-language query: anchors ("like Hades") + filters ("co-op") | Should | Anchor titles resolve to catalogue IDs; filters applied; unresolved terms reported | US-06 | M3 |
| FR-19 | `whyfinder eval` writes metrics JSON and a Markdown report with intervals | Must | Report produced on every CI gate run | US-09 | M1 |
| FR-20 | Quality-gate PR comment; merge blocked on significant regression | Must | See 07_EVALUATION.md | US-09 | M1 |
| FR-21 | REST API: `/recommend`, `/explain`, `/search`, `/healthz`, `/version` | Must | OpenAPI committed; Schemathesis contract tests pass | US-01 | M4 |
| FR-22 | Star-atlas web demo (TypeScript) on GitHub Pages with a live in-browser engine (ADR-0015) | Should | Works from exported artifacts with no server; the TypeScript engine reproduces the Python goldens (1e-9, identical picks); axe 0 violations, light and dark | US-08 | M0–M4 |
| FR-23 | Filters: tag, price, release year | Should | Filtered picks never violate a filter; empty results explained | US-07 | M3 |

## Non-functional requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-01 | Reproducibility | Fixed seeds; `uv.lock`; DVC pipeline; a rerun on CPU gives identical metrics |
| NFR-02 | Training time | EASE + PPR + blend on full data < 15 min on a laptop CPU; CI subsample < 3 min |
| NFR-03 | Memory | Peak < 8 GB on full data (item cap is a parameter; see ADR-0004) |
| NFR-04 | Serving latency | p95 < 150 ms for top 10 without the LLM |
| NFR-05 | Code quality | ruff clean; mypy strict on `core`, `graph`, `explain`, `rerank`; core coverage ≥ 85% |
| NFR-06 | Cost | $0 by default: local LLM via Ollama; CI replays cached generations and never calls a paid API |
| NFR-07 | Data ethics | Usernames hashed; quotes ≤ 25 words; dataset cited; raw data never redistributed |
| NFR-08 | Security | No secrets in the repo; Pydantic validation on every input; API rate limit |
| NFR-09 | Accessibility | Demo keyboard-usable; axe 0 violations; reduced motion respected |
| NFR-10 | Documentation | Every decision as an ADR; README numbers generated from `results/` |
