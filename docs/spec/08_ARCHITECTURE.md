# 08 · Architecture

One Python package with strict internal layers, an offline pipeline that produces versioned
artifacts, a thin API that only reads them, and a static TypeScript demo. The diagrams follow the C4
model (context → containers → components) and render on GitHub.

## C1 · Context

```mermaid
flowchart LR
  player([Player]) -->|picks games, asks why| demo[Whyfinder demo<br/>GitHub Pages]
  reviewer([Reviewer]) -->|reads code, CI, docs| repo[GitHub repo]
  demo -->|optional live calls| api[Whyfinder API]
  ucsd[(UCSD Steam datasets)] -->|download by script| pipeline[Offline pipeline]
  pipeline -->|release artifacts| demo
  pipeline -->|release artifacts| api
```

## C2 · Containers

```mermaid
flowchart TB
  subgraph offline[Offline: laptop, or CI on a 5% sample]
    raw[(Raw files)] --> dvc[DVC pipeline<br/>fetch · parse · clean · kcore · split]
    dvc --> feat[Features<br/>X_train, catalogue]
    feat --> models[Model build<br/>EASE^R · game graph + PPR · blend M · iALS rival]
    feat --> idx[Review index<br/>chunks · BM25 · embeddings · HNSW]
    models --> eval[Evaluate + gates<br/>paired bootstrap]
    idx --> eval
  end
  models --> art[(Versioned artifacts<br/>M.npz · graph.npz · hnsw.bin · catalogue)]
  idx --> art
  art --> api[FastAPI service<br/>/recommend · /explain · /search]
  art -->|whyfinder export demo| web[Star-atlas demo<br/>TypeScript, live engine in a Web Worker]
  api --> ollama[Ollama<br/>local LLM]
  web -.->|optional| api
```

## C3 · Components (package `whyfinder`)

| Package | Responsibility | May import | Never imports |
| --- | --- | --- | --- |
| `data` | fetch, parse, clean, contracts, split | numpy, pandas, pandera | `serve` |
| `core` | popularity, item-kNN, EASE^R, iALS, blend scoring | numpy, scipy | anything else in whyfinder |
| `graph` | game graph build, PPR forward push, Π | numpy, scipy, `core` (types) | `serve`, `rag` |
| `rerank` | DPP greedy MAP, filters | numpy, `core` (types) | `serve` |
| `explain` | attributions, counterfactuals, paths, variety flag | `core`, `graph`, `rerank` | `rag`, `serve` |
| `rag` | chunking, BM25, HNSW, RRF, generation, claim checker, cache | `explain` (types), `core` (types) | `serve`, `eval` |
| `eval` | metrics, bootstrap, gates, reports | everything except `serve` | `serve` |
| `serve` | FastAPI app, Pydantic schemas | everything except `eval` | (nothing imports it) |
| `cli` | Typer entry point | everything | — |

Enforced by **import-linter** contracts in `pyproject.toml`, checked in CI.

## Request flow: `/explain`

```mermaid
sequenceDiagram
  participant W as Web demo
  participant A as API
  participant C as core + rerank
  participant E as explain
  participant R as rag
  participant L as Ollama
  W->>A: POST /explain {liked_game_ids, game_id}
  A->>C: score (x_u · M), filter, top 100, DPP
  C-->>A: top 10 + scores
  A->>E: attributions, counterfactual, paths, variety flag
  E->>C: re-run pipeline per candidate removal
  E-->>A: exact reasons
  A->>R: retrieve chunks for shared aspects (BM25 + HNSW + RRF)
  R->>L: grounded prompt (cached by hash)
  L-->>R: claims JSON
  R->>R: claim checker → regenerate once → template fallback
  R-->>A: verified claims
  A-->>W: reasons + claims + evidence IDs
```

## Repository layout

```
whyfinder/
├─ src/whyfinder/{data,core,graph,rerank,explain,rag,eval,serve}/, cli.py
├─ tests/{unit,property,golden,contract}/
├─ web/                 Star-atlas demo (Vite + Svelte + TypeScript), live engine on an exported slice
├─ docs/{spec,decisions,plan,guide,design}/
├─ results/             metrics JSON the README tables are generated from
├─ scripts/             bootstrap_github.py, gen_readme_tables.py
├─ docker/              Dockerfile.api (multi-stage, non-root)
├─ .github/             workflows, issue and PR templates, CODEOWNERS, dependabot
├─ dvc.yaml  params.yaml  pyproject.toml  uv.lock  Makefile  CITATION.cff
```

## Determinism rules

- No wall-clock time or unseeded randomness in `core`, `graph`, `rerank`, `explain`, `eval`: seeds are
  passed in; clocks are injected.
- Every tie broken by game ID.
- Functions are pure and never mutate inputs; arrays passed in are treated as read-only.
