# Whyfinder documentation

| Folder | What's inside |
| --- | --- |
| [spec/](spec/) | The specification, numbered in reading order |
| [decisions/](decisions/README.md) | Architecture decision records (ADR-0001 … 0016) |
| [plan/](plan/) | [Roadmap](plan/ROADMAP.md), [risks](plan/RISKS.md), [backlog](plan/BACKLOG.csv) (imported as issues by `scripts/bootstrap_github.py`) |
| [guide/](guide/) | [Implementation, step by step](guide/IMPLEMENTATION.md), [workflow](guide/WORKFLOW.md), [glossary](guide/GLOSSARY.md) |
| [design/](design/) | Tokens, logo and screenshots of the demo (Unmasked, ADR-0018) |

## Spec, in reading order

| # | Document | One line |
| --- | --- | --- |
| 00 | [Vision](spec/00_VISION.md) | What, why, research question, why this algorithm mix |
| 01 | [PRD](spec/01_PRD.md) | Personas, user stories, success metrics |
| 02 | [Requirements](spec/02_REQUIREMENTS.md) | FR-01…23, NFR-01…10 with acceptance criteria |
| 03 | [Data](spec/03_DATA.md) | Sources, terms, pipeline, contracts, split |
| 04 | [Algorithms](spec/04_ALGORITHMS.md) | EASE^R, PPR push, blend, DPP, counterfactuals, iALS, BM25, HNSW, RRF |
| 05 | [Explainability](spec/05_EXPLAINABILITY.md) | Attributions, counterfactuals, paths, variety flag, how they're measured |
| 06 | [RAG](spec/06_RAG.md) | Corpus, retrieval, grounded generation, claim checker |
| 07 | [Evaluation](spec/07_EVALUATION.md) | Metrics, sealed test set, bootstrap gates |
| 08 | [Architecture](spec/08_ARCHITECTURE.md) | C4 diagrams, components, boundaries, request flow |
| 09 | [CI/CD and MLOps](spec/09_CICD_MLOPS.md) | Workflows, versioning, environments |
| 10 | [Testing](spec/10_TESTING.md) | Test levels and oracles |
| 11 | [Design system](spec/11_DESIGN_SYSTEM.md) | Star Atlas: themes, type, components, motion, accessibility |
| 12 | [API](spec/12_API.md) | Endpoints and contracts |

Model card: template in [model-card-template.md](model-card-template.md); `docs/model-card.md` is generated at each release.
