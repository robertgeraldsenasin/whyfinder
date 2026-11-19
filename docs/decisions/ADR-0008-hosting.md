# ADR-0008: Hosting: static demo on GitHub Pages, optional live API

- **Status:** Accepted (demo 2026-11-17; API settled by ADR-0019 on 2026-11-20)
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

The demo must stay up for free; a live API is nice but not required.

## Options considered

1. GitHub Pages only (precomputed JSON)
2. Render
3. Fly.io
4. Hugging Face Spaces
5. Google Cloud Run

## Decision

Ship the demo as static JSON on GitHub Pages (works with no server). Decide the optional API host in M4 after checking current free-tier terms; record the choice and its limits here.

Since ADR-0015 the demo runs the glass-box engine itself in the browser, so GitHub Pages hosts the
whole live demo, not only precomputed results. `pages.yml` deploys after `ci` passes on `main` and a
health check loads the page, the slice and the model constants.

The API ships as a container image on GHCR with no always-on host (ADR-0019).

## Consequences

The portfolio link never breaks; live explanations for arbitrary queries depend on the API host.
