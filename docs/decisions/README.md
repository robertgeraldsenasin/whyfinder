# Decision records

Architecture decision records in the Hasik format (context, options, decision, consequences). A decision changes only through a new ADR that supersedes the old one.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](ADR-0001-python-core-hand-written-algorithms.md) | Python core, hand-written algorithms, libraries as oracles | Accepted |
| [0002](ADR-0002-interactions-and-time-split.md) | Interactions from dated reviews, global time split | Proposed (confirm in M0) |
| [0003](ADR-0003-pipeline-and-data-versioning.md) | DVC pipeline; CI uses a pinned subsample | Proposed |
| [0004](ADR-0004-item-cap-and-confidence.md) | Item cap for EASE^R and confidence weighting | Proposed |
| [0005](ADR-0005-gate-statistics.md) | Quality gates: paired bootstrap non-inferiority, sealed test set | Accepted |
| [0006](ADR-0006-targets-and-margins.md) | Success targets and gate margins | Proposed (fix after M1 baselines) |
| [0007](ADR-0007-glass-box-blend.md) | Glass-box blend: EASE^R + Personalized PageRank, iALS as rival | Accepted |
| [0008](ADR-0008-hosting.md) | Hosting: static demo on GitHub Pages, optional live API | Proposed (decide in M4) |
| [0009](ADR-0009-llm-runtime.md) | LLM: local model through Ollama, cached in CI | Accepted |
| [0010](ADR-0010-retrieval.md) | Retrieval: hybrid BM25 + dense on our own HNSW, merged by RRF | Proposed (embedding model chosen in M3) |
| [0011](ADR-0011-dpp-reranking.md) | DPP re-ranking for variety | Accepted |
| [0012](ADR-0012-counterfactual-guarantees.md) | Counterfactual search modes and guarantees | Accepted |
| [0013](ADR-0013-design-language.md) | Design language: Star Atlas | Accepted (motion amended by 0016) |
| [0014](ADR-0014-name.md) | Name: Whyfinder | Accepted |
| [0015](ADR-0015-live-engine-demo.md) | A live glass-box engine in the browser, built alongside the core | Accepted |
| [0016](ADR-0016-cinematic-motion.md) | Cinematic motion for the Star Atlas | Accepted |

New ADR: copy [ADR-template.md](ADR-template.md), take the next number, open a PR labelled `type:docs`.
