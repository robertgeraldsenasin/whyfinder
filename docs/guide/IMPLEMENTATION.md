# Implementation guide, step by step

How Whyfinder is built, in the order it was built, with the commands to reproduce each step on your
own machine. Every step names the files that implement it and the test that proves it. Status as of
**November 17, 2026**: steps 1–7 are done; step 8 lists what comes next, milestone by milestone.

```mermaid
flowchart LR
  A[1 Repo + CI] --> B[2 Data pipeline]
  B --> C[3 Demo slice]
  C --> D[4 Python core]
  D --> E[5 Browser engine + goldens]
  E --> F[6 Star Atlas UI]
  F --> G[7 Pages deploy]
  G --> H[8 Next: M1 to M4]
```

## 0 · Set up your machine (once)

Windows, macOS or Linux. You need Git, [uv](https://docs.astral.sh/uv/) (Python 3.12+), Node.js 22
and, optionally, the GitHub CLI.

```bash
git clone https://github.com/robertgeraldsenasin/whyfinder.git
cd whyfinder
uv sync --group dev          # Python tools and the package
make verify                  # lint, format, mypy --strict, import boundaries, pytest + coverage
cd web && npm ci && npm test # the browser engine against the Python goldens
npm run dev                  # the demo on http://localhost:5173/whyfinder/
```

On Windows without `make`, run the five commands under `verify:` in the `Makefile` one by one.

## 1 · Repository, rules and CI ✅

- **What:** uv package `whyfinder` (src layout), strict layers checked by import-linter, Conventional
  Commits, one issue → one branch → one PR → squash merge.
- **Where:** `pyproject.toml` (ruff, mypy, pytest, coverage ≥ 85%, import contracts), `Makefile`,
  `.github/workflows/ci.yml` (jobs `python 3.12`, `python 3.13`, `web`).
- **Proof:** CI must be green to merge.

## 2 · Data pipeline (M0) ✅

| Stage | Command | What it guarantees | Code · test |
| --- | --- | --- | --- |
| fetch | `whyfinder data fetch` | every raw byte matches `data/checksums.txt` | `data/fetch.py` · `test_fetch.py` (network mocked) |
| parse | `whyfinder data parse --workers 4` | Python-literal lines parsed with `ast.literal_eval`; ≤ 0.1% malformed | `data/parse.py` · `test_parse.py` |
| clean | `whyfinder data clean` | hashed users, one row per (user, game), hours clipped, entities decoded; Pandera contracts | `data/clean.py`, `data/contracts.py` |
| kcore | `whyfinder data kcore` | every user and game has ≥ 5 interactions | `data/kcore.py` · Hypothesis property test |
| split | `whyfinder data split` | global time cut-offs; no test row before T2; cold-start set | `data/split.py` · `test_split.py` |
| features | `whyfinder data features` | X_train with confidence weights, 8,000-game cap | `data/features.py` |
| subsample · stats | `whyfinder data subsample`, `whyfinder data stats` | pinned 5% CI sample; `data/stats.json` | `data/subsample.py`, `data/pipeline.py` |

**Run it on GitHub (recommended):** Actions → **data** → *Run workflow*. About 5 minutes on a GitHub
runner; it publishes the release `data-ci-v1` with the subsample, `stats.json`, `split.json`,
`dvc.lock` and the demo slice (ADR-0003).

**Run it on your laptop** (about 4 GB free disk, 8 GB RAM):

```bash
uv sync --group pipeline
uv run whyfinder data fetch      # verifies data/checksums.txt
uv run dvc repro                 # every stage in order; only changed stages re-run
```

Results of the first full run are in `data/stats.json` and ADR-0002: 7.79 M reviews, 0 malformed,
100% dated, T1 = 2017-05-31, T2 = 2017-10-01.

## 3 · Demo slice ✅

`uv run whyfinder export demo` writes the 500 most-played games with their co-play Gram matrix
G = XᵀX (train split only), metadata and a deterministic star-map layout. Aggregates only: no user
rows, no review text. Copy it to `web/public/data/demo-slice.json` (the data run publishes it).

## 4 · The glass-box core in Python ✅ (on the slice; full-data build in M1)

| Algorithm | File | Oracle / property test |
| --- | --- | --- |
| EASE^R | `core/ease.py` | numpy inverse on 300 items to 1e-8; Steck's normal equations; diag(B) = 0 |
| Game graph | `graph/build.py` | graph contract: symmetric, weights > 0, every game linked |
| PageRank by forward push | `graph/ppr.py` | power iteration on a 2,000-node graph within ε·deg(v); truncation loss reported |
| Blend + scoring | `core/blend.py` | scores bit-for-bit additive (Hypothesis) |
| Pipeline (filter, top 100, DPP) | `rerank/pipeline.py`, `rerank/dpp.py` | greedy steps equal naive determinant ratios on 12 candidates |
| Attributions | `explain/attributions.py` | Σ contributions = score within 1e-9 (Hypothesis) |
| Counterfactuals | `explain/counterfactual.py` | valid and irreducible by full re-runs; exact search never larger |
| "Related by" paths | `explain/paths.py` | every path exists in the graph |

`uv run whyfinder export model` builds the model on the slice and writes `web/public/data/model.json`
(parameters, c_B, c_Π, truncation loss) and the goldens. `tests/golden/test_web_goldens.py` fails if
the committed goldens no longer match the Python code.

## 5 · The browser engine and the golden cross-check ✅

`web/src/engine/` is a second, hand-written implementation of every algorithm above, operation for
operation (ADR-0015). `npm test` (Vitest) requires it to reproduce the Python goldens on five
histories: B rows, graph degrees, push rounds and estimates, Π rows, candidates, scores, picks, variety
flags, DPP gains, attributions, counterfactual sets and paths. **When you change an algorithm, change
both sides, run `uv run whyfinder export model`, and commit the new goldens in the same PR.**

## 6 · The Star Atlas UI ✅

| View | What it shows | Files |
| --- | --- | --- |
| Discover | your games as white stars, picks as amber sparkles, reasons as lines with light flowing at their exact share; why panel with the EASE^R/PageRank split, the counterfactual and paths | `web/src/lib/views/Discover.svelte`, `components/` |
| Under the hood | the same run replayed stage by stage from the engine's traces: confidence weights, the Cholesky sweep over G, push rounds spreading mass, the β blend, the shortlist, each DPP step, the counterfactual trail | `views/UnderTheHood.svelte` |
| Architecture | the system as a live diagram with real numbers; replay a request (your timings) or the build (the data run's counts) | `views/Architecture.svelte` |

The engine runs in a Web Worker (`engine/worker.ts`), so animations never wait for maths. Design:
`docs/spec/11_DESIGN_SYSTEM.md` and ADR-0016 (cinematic map, solid reading panels, reduced motion
respected). `npm run e2e` runs Playwright on desktop and phone, with axe in both themes.

## 7 · Deploy ✅

`pages.yml` builds `web/` after `ci` passes on `main`, deploys to GitHub Pages and runs a health check
(page, slice and model load). One-time setting: **Settings → Pages → Source: GitHub Actions**.

## 8 · What comes next

| Milestone | Steps |
| --- | --- |
| **M1 · glass-box core + gate** (to Dec 12) | `whyfinder build`: EASE^R at the 8,000-game cap with peak memory logged, the full graph and Π, sparse scoring (#13, #16) · popularity and item-kNN baselines (#12) · iALS rival with the `implicit` oracle (#17) · metrics, paired bootstrap, Holm, `whyfinder eval` (#18) · `quality-gate.yml` with the PR comment (#19) · tune β, λ, θ and M_Π on validation: the demo slice already shows a popularity pull (Team Fortress 2 tops many lists) and a 44% mean Π truncation loss at M_Π = 200 · README tables from `results/` (#20) · tag v0.1.0 |
| **M2 · explanations + variety** (to Dec 30) | offline exact counterfactuals and the minimality-gap metric (#24) · iALS counterfactuals by Sherman–Morrison (#25) · θ tuned for diversity (#26) · explanation checks in the gate (#28) · tag v0.2.0 |
| **M3 · grounded RAG** (to Jan 13) | review chunks + BM25 (#31) · embeddings + hand-written HNSW + RRF (#32) · 150 labelled queries (#33) · Ollama generation, claim checker, fallback, cache (#34) · natural-language queries and filters (#35) |
| **M4 · API, demo finish, v1.0** (to Jan 24) | FastAPI + Docker (#36) · query bar, filters, API mode and the "Words" stage in the demo (#37) · sealed test-set results, model card, case study (#39) |

## Troubleshooting

- **`make verify` fails on formatting:** `uv run ruff format .`
- **Vitest says a golden differs:** you changed one engine but not the other, or forgot
  `uv run whyfinder export model`.
- **Playwright can't find a browser locally:** `npx playwright install chromium`, or set
  `WHYFINDER_CHROME` to an installed Chrome.
- **The data run fails at fetch with a checksum mismatch:** the UCSD files changed. Investigate
  before re-recording: `whyfinder data fetch --record` only for files that have no checksum yet.
