# Whyfinder

Explainable Steam game recommender. Python 3.12+ (uv), src layout, package `whyfinder`.
Spec: docs/spec/ (start with 00_VISION.md). Decisions: docs/decisions/. Plan: docs/plan/ROADMAP.md.

## Commands

- Install: `uv sync --group dev`
- Everything CI checks: `make verify` (ruff lint + format check, mypy strict, import-linter, pytest + coverage)
- Tests only: `uv run pytest` (one file: `uv run pytest tests/unit/test_package.py`)
- CLI: `uv run whyfinder --help`
- Pipeline (from M0): `uv run dvc repro`

## Authorship (owner's standing rule)

- Every commit is authored AND committed as `Robert Gerald Senasin <robertgeraldsenasin@gmail.com>`.
- No `Co-Authored-By`, no "Generated with", no session links, no mention of Claude or AI tools in
  commits, PR titles or bodies, issues, review comments or code comments. Interactions stay in the chat.
- In Claude sessions, GitHub GraphQL is blocked: use REST (`gh api repos/<owner>/<repo>/pulls --method POST --input pr.json`,
  merge with `PUT /repos/<owner>/<repo>/pulls/<n>/merge` and `merge_method: squash`). Push with
  `git -c push.negotiate=true push`.

## Rules

- Core algorithms are hand-written; reference libraries are test oracles only (ADR-0001).
- No wall-clock time or unseeded randomness in `core`, `graph`, `rerank`, `explain`, `eval`. Pass seeds and clocks in.
- Pure functions; never mutate input arrays. Break every tie by game ID.
- Respect the import boundaries in pyproject (`lint-imports`): `core` imports nothing else in whyfinder; nothing imports `serve`.
- Every new module gets tests, failure paths too; every algorithm gets an oracle or property test (docs/spec/10_TESTING.md).
- Attributions must stay exact: any change to scoring keeps `sum(contributions) == score` within 1e-9.
- The test split is sealed: never read test-set metrics outside `release.yml`.
- README numbers come only from `results/` via `scripts/gen_readme_tables.py`.
- A changed decision needs a new or updated ADR in docs/decisions/.
- UI work follows docs/spec/11_DESIGN_SYSTEM.md and docs/design/tokens.css (one accent per view; reduced motion; axe 0 violations).

## Workflow

One issue → one branch (`feat/<issue>-<slug>`) → one PR citing requirement IDs (FR-xx) → CI green → squash merge.
Conventional Commits. Milestone done = gates green on main + tagged release + CHANGELOG.

## Definition of done

`make verify` passes; acceptance criterion from docs/spec/02_REQUIREMENTS.md met in CI; tests include a
failure path; docs/ADR updated if a decision changed; no new warnings.
