# Changelog

All notable changes are recorded here, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Tuned on full-data validation (5,000 users, 8,000 games; `results/validation/tune-2026-11-19.json`): blend β 0.5 → 0.25, DPP θ 2 → 1, item-kNN shrinkage 10 → 50, iALS reg 0.01 → 0.1 and α 10 → 5. The demo's model and goldens are rebuilt from them.
- ADR-0006 accepted with the real baselines: the diversity target is now a share of the ILD headroom (relevance-only lists already reach 0.81), and the explanation checks run on 1,000 users with a deletion margin of 0.02.
- Proved the quality gate fails a deliberately worse model (PR #74; `docs/evidence/gate-proof.md`).

### Added

- iALS explanations (FR-11, #25): exact attributions for the rival and counterfactuals whose re-scoring uses Sherman–Morrison downdates instead of fresh solves, checked against a fresh solve to 1e-8 (`explain/ials.py`).
- The REST API (FR-21, ADR-0019): `POST /recommend`, `POST /explain`, `GET /search`, `GET /healthz` and `GET /version`, serving the same model as the live demo, so the picks and their reasons agree.
  - a taste is liked Steam app IDs, a description in the demo's words, or both; the API's parser is the demo's twin and both are tested on the same cases;
  - `/explain` returns the exact attributions (EASE and graph parts), the irreducible counterfactual, the graph paths and template claims checked against the attributions;
  - errors are `application/problem+json`; bodies are capped at 16 KB; 30 requests a minute per client on `/explain` and 120 on the rest; inputs are strict, so the server rejects exactly what the schema rejects;
  - `docs/openapi.json` is committed and a test fails if it drifts (`whyfinder serve openapi`); Schemathesis checks the running app against it;
  - `whyfinder serve run`, and a Docker image (`docker/Dockerfile.api`) that CI builds and smoke-tests on every PR and pushes to GHCR from `main`.

- Describe what you want (FR-18, FR-23): "like Portal 2, co-op, under $20, after 2012" adds the named games to your sky and sets tag, price and release-year filters, shown as removable chips; anything not understood is said back. Filters remove games before the shortlist, so no pick can break one; a short or empty hand says which filters are responsible. The parser is deterministic (`web/src/lib/query.ts`) and keeps titles with commas whole.

- Evaluation and the quality gate (M1: FR-04, FR-09, FR-19, FR-20):
  - baselines: popularity and item-kNN (cosine with shrinkage, top 100 per game), checked against the dense formula;
  - iALS, the latent-factor rival, hand-written with an exact Cholesky solver and a batched, warm-started conjugate-gradient solver; checked against the dense normal equations and the dense objective, and its loss falls every sweep;
  - per-user metrics: NDCG@10, Recall@20, MRR, catalogue coverage@10, intra-list diversity@10 and average recommendation popularity@10;
  - paired bootstrap of the mean difference with a non-inferiority p-value, and Holm–Bonferroni across the gated metrics;
  - `whyfinder eval` (every model on the same held-out users; the test split refuses to run outside a release), `whyfinder gate` and `whyfinder results`;
  - `whyfinder tune` and the manual `tune.yml` workflow: fixed-budget grids on validation for EASE^R's λ, item-kNN's shrinkage, iALS's regularisation and confidence, the blend's β and DPP's θ (the highest diversity within 0.005 NDCG@10 of the blend);
  - explanation checks on each user's first pick (05_EXPLAINABILITY.md): additivity and counterfactual validity must hold for every user; the deletion test (removing the three most-attributed games pushes the pick down further than three random ones) and the greedy-versus-exact minimality gap are gated non-inferior; a shuffled-model rank correlation is reported as a sanity check;
  - `quality-gate.yml` runs on every model PR against main on the CI subsample and keeps one PR comment up to date; `release.yml` scores the sealed test set on a tag; the nightly job reports validation numbers; the data pipeline gains an `eval_valid` stage.

- Unmasked, the demo's new design language (ADR-0018, FR-22):
  - a stage at night in crimson, bone and ink, with violet for the graph; Anton poster type, Prata for names, Comic Relief for what players wrote;
  - the ten picks are dealt as a hand of cards, Ace to 10, and each card's suit says which part of the model carried it (hearts: players in common; clubs: tags and studios), computed from the exact attributions;
  - the pick is a card face with the Steam art, the closeness tier stamped on it and a line saying how much of the score its suit carried;
  - the deal: a spotlight lock-on, cards that turn over as they fall and burst into their stars, comic impact frames with halftone, a burst and confetti for the Ace;
  - a centred title screen with an admission-ticket search and four starter hands fanned like cards;
  - sounds for dealing a card and a short brass flourish for the Ace;
  - screenshots of every view, desktop and phone, kept by CI (`npm run screens`).

- Review evidence (`whyfinder export reviews`, DVC stage `export_reviews`):
  - community terms per game, by log-odds with an informative Dirichlet prior;
  - twelve specific, positive quotes of at most 25 words, chosen to cover the game's neighbour games so the demo can quote players who also played yours.
- Starfall, a new design language for the demo (ADR-0017):
  - midnight sky, gold and violet; Prata for the slashed wordmark and titles, Josefin Sans for the interface, Cutive Mono for player quotes; cut-corner frames and slanted buttons;
  - picks fall into the sky with beams, impact frames, shockwaves, embers and shake;
  - the sky recolours by closeness (√ of the relative score, five named tiers, three colour modes);
  - synthesized sound effects;
  - settings for colours, sound and impact effects.
- Pick panel with Steam art and store link, exact shares, bridge quotes, shared community terms, the counterfactual and how the pick connects to your games.

### Changed

- The light theme is retired; ADR-0013's palette and type are superseded by ADR-0017.
- Starfall's palette, type, frames and fall visuals are superseded by Unmasked (ADR-0018); saved colour settings carry over. Cutive Mono is no longer used.

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
