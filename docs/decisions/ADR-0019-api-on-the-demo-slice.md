# ADR-0019: The API serves the demo-slice model and ships as an image

- **Status:** Accepted
- **Date:** 2026-11-20
- **Deciders:** Robert Gerald Senasin

## Context

FR-21 asks for a REST API with an OpenAPI document and contract tests. ADR-0008 left the API host
open until M4. The full-data model needs the raw dataset and a DVC run to build, and its matrices are
too large to commit. The demo already runs a model built by the Python core on a committed 500-game
slice, and the browser engine reproduces it exactly (ADR-0015).

## Options considered

1. Serve the full-data model: build artifacts in the pipeline and load them at start-up.
2. Serve the demo-slice model: the same slice and params the goldens are made from.
3. A free always-on host (Render, Fly.io, Hugging Face Spaces, Cloud Run) for either.

## Decision

The API serves option 2 (`model_version` `blend-slice-1`), so a pick and its reasons from the API are
the demo's for the same games. The loader takes any file in the slice format, so a bigger export can
be served later without changing the endpoints.

Requests carry no play time, so every liked game gets the confidence of zero hours. One liked game is
enough (the spec said three; the demo deals from one). Unknown IDs are listed in the response;
a taste with no known game is a 404.

The image (`docker/Dockerfile.api`) is built and smoke-tested on every pull request and pushed to
GHCR from `main`. No always-on host for now: free tiers sleep, change terms often, and the demo does
not need a server. Anyone can run the image locally or on a container host of their choice.

## Consequences

- The API knows 500 games; queries about others come back as unknown, by design.
- API and demo cannot drift: the pytest contract and the golden tests pin the same model.
- Rate limits are per process (in memory). Behind a proxy, uvicorn's `--proxy-headers` must be on so
  the limit sees client addresses; `whyfinder serve run` turns it on.
- ADR-0008's open question is closed by this record.
