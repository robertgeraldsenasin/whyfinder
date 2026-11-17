<p align="center">
  <img src="docs/design/logo.svg" width="96" alt="Whyfinder logo: four stars joined in a Y">
</p>

<h1 align="center">Whyfinder</h1>
<p align="center"><b>Find your next game. Know why.</b></p>

<p align="center">
  <a href="https://github.com/robertgeraldsenasin/whyfinder/actions/workflows/ci.yml"><img src="https://github.com/robertgeraldsenasin/whyfinder/actions/workflows/ci.yml/badge.svg" alt="ci"></a>
  <img src="https://img.shields.io/badge/python-3.12%20%7C%203.13-1f6feb" alt="Python 3.12 and 3.13">
  <img src="https://img.shields.io/badge/license-MIT-0e8a16" alt="MIT licence">
</p>

Whyfinder recommends Steam games and shows, in a form you can check, **why** it picked each one.
Every reason is the model's actual reason, computed exactly, and CI proves every change keeps it that
way.

> **Status:** M0, foundation. Numbers below appear when the first gated release (v0.1) ships.
> Roadmap: [docs/plan/ROADMAP.md](docs/plan/ROADMAP.md).

## How it works

| Layer | What it does | Spec |
| --- | --- | --- |
| **Glass-box blend** | EASE^R (closed-form item-item model) + Personalized PageRank over a game–tag–developer–co-play graph, blended into one item-item matrix | [04 §A2–A5](docs/spec/04_ALGORITHMS.md) |
| **Exact reasons** | Both models are additive over your history, so "42% from Dead Cells" is exact, and the smallest set of your games that removes a pick is found by re-scoring, not guessing | [05](docs/spec/05_EXPLAINABILITY.md) |
| **Variety** | DPP greedy MAP re-ranking keeps the top 10 from being ten copies of one game; picks kept for variety say so | [04 §A6](docs/spec/04_ALGORITHMS.md) |
| **Grounded words** | Hybrid BM25 + dense retrieval (hand-written HNSW) over reviews; a local LLM may only voice the exact reasons; a claim checker rejects anything unverifiable | [06](docs/spec/06_RAG.md) |
| **The rival** | iALS, a latent-factor model the glass-box blend must match | [04 §A3](docs/spec/04_ALGORITHMS.md) |
| **Gates** | Paired-bootstrap non-inferiority on ranking, explanation and RAG metrics for every PR; a sealed test set scored only at release | [07](docs/spec/07_EVALUATION.md) |

Architecture (C4 diagrams): [docs/spec/08_ARCHITECTURE.md](docs/spec/08_ARCHITECTURE.md).
Design language ("Star Atlas"): [docs/spec/11_DESIGN_SYSTEM.md](docs/spec/11_DESIGN_SYSTEM.md).
Decisions: [docs/decisions/](docs/decisions/README.md).

## Quick start

```bash
uv sync --group dev        # Python 3.12+
make verify                # lint, format, types, import boundaries, tests
uv run whyfinder version
```

`make reproduce` (from M1) rebuilds every number in this README from the raw data.

## Results

<!-- results:start -->
_Generated from `results/` at each release. None yet._
<!-- results:end -->

## Data and citation

Steam data from the UCSD McAuley Lab (<https://cseweb.ucsd.edu/~jmcauley/datasets.html>), downloaded by
script and never redistributed. Please cite the dataset papers listed in [CITATION.cff](CITATION.cff).

## License

MIT © 2026 Robert Gerald Senasin
