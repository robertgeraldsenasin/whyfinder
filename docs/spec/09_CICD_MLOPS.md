# 09 · CI/CD and MLOps

Five GitHub Actions workflows take a change from PR to a released model and a live demo. CI never
downloads the 1.3 GB raw data: it uses a processed, checksum-pinned subsample published as a release
asset (`data-ci-v1`).

| Workflow | Trigger | Jobs | Fails when |
| --- | --- | --- | --- |
| `ci.yml` | every push and PR | `uv sync --frozen`; ruff (lint + format); mypy strict; import-linter; pytest (unit, property, golden, contract) with coverage; web: lint, typecheck, Vitest, build, Playwright + axe (from M4) | any check fails; core coverage < 85% |
| `quality-gate.yml` | PRs touching `src/whyfinder/` (except `serve`), `params.yaml`, `dvc.yaml` | fetch the pinned subsample; build base (main) and head with the same seeds; `whyfinder gate`; post or update the PR comment | a gate in 07_EVALUATION.md fails |
| `nightly.yml` | daily 19:17 UTC (03:17 Manila) | full validation report on the subsample; iALS stability over 3 seeds; `pip-audit`, `npm audit` | high-severity advisory |
| `release.yml` | tag `v*` | score the sealed test set; write `results/`; regenerate README tables; build the API image to GHCR; GitHub Release with model card | test-set numbers can't be produced |
| `pages.yml` | after `release.yml`, or manual | build `web/` with exported artifacts; deploy to Pages; post-deploy health check | health check fails |

In the scaffold, only `ci.yml` is active; the others carry `workflow_dispatch` only until their milestone
(the comment at the top of each file says when to switch the trigger on).

## Versioning

| What | Tool | Notes |
| --- | --- | --- |
| Code | Git, Conventional Commits, SemVer tags | squash merges; `CHANGELOG.md` (Keep a Changelog) |
| Data + pipeline | DVC (`dvc.yaml`, `params.yaml`, `dvc.lock`) | remote chosen in ADR-0003 |
| Experiments | MLflow, local file store | params, metrics, per-user arrays, plots |
| Models | MLflow registry: `whyfinder-blend` with aliases `champion` / `challenger` | promoted only by `release.yml` after gates pass |
| Model card | `docs/model-card.md` per release (Mitchell et al., FAT* 2019) | data, intended use, metrics with intervals, limits |

## Environments

| Environment | Runs | Purpose |
| --- | --- | --- |
| Local | `uv` + Docker Compose (API, Ollama) | development, full-data builds, RAG cache generation |
| CI | GitHub-hosted Ubuntu | checks and gates on the subsample |
| Demo | GitHub Pages | static star-atlas demo |
| API (optional) | container from GHCR on a free tier (ADR-0008) | live `/recommend`, `/explain` |

## Security and supply chain

- Dependabot for pip (uv), npm and Actions, grouped weekly.
- Actions pinned to major versions; `permissions:` least privilege per job.
- No secrets needed for CI (no paid APIs). Optional hosted-LLM key only in local `.env` (git-ignored).
