# Changelog

All notable changes are recorded here, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.0.1] - 2026-11-17

M0 Foundation: the repository, the data pipeline and its first full run, and the live star-atlas demo
(<https://robertgeraldsenasin.github.io/whyfinder/>).

### Added

- Project scaffold: uv package `whyfinder`, CLI, CI (ruff, mypy strict, import-linter, pytest + coverage).
- Specification (docs/spec 00–12), 14 decision records, roadmap, risks, backlog and the Star Atlas design system.
- ADR-0015 (live glass-box engine in the browser, built alongside the core) and ADR-0016 (cinematic motion); demo-track issues in the backlog.
- Data pipeline (M0): checksummed fetch, streaming parser, cleaning with Pandera contracts, k-core, global time split with a cold-start set, the training matrix, the pinned CI subsample, `data/stats.json`; DVC stages and the manual `data.yml` workflow that runs it on GitHub and publishes `data-ci-v1`.
- First full data run recorded; ADR-0002 and ADR-0003 accepted.
- Glass-box core on the demo slice: EASE^R, the game graph, PageRank by forward push (synchronous rounds), the blend, DPP re-ranking, exact attributions, greedy and exact counterfactuals, "related by" paths, each with an oracle or property test.
- `whyfinder export demo` and `whyfinder export model`; the TypeScript engine in `web/src/engine/` reproduces the Python goldens (Vitest).
- Star Atlas web demo: Discover, Under the hood and Architecture views; Playwright + axe in CI; deployed to GitHub Pages by `pages.yml` with a health check.
- `docs/guide/IMPLEMENTATION.md`: the step-by-step build guide.
- `tidy-text` workflow: keeps owner-written issue and pull request text free of appended tool footers.

### Fixed

- HTML entities (including doubly escaped ones) in game titles, developers, publishers and tags.

[Unreleased]: https://github.com/robertgeraldsenasin/whyfinder/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/robertgeraldsenasin/whyfinder/releases/tag/v0.0.1
