# ADR-0015: A live glass-box engine in the browser, built alongside the core

- **Status:** Accepted
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

The original plan (FR-22, M4) shipped the demo last, as a viewer for JSON precomputed by the Python
pipeline. Two problems with that:

1. A precomputed demo can only replay fixed histories. It can't show the algorithms *working*, which is
   the point of a glass-box recommender and what a reviewer wants to see in ten minutes.
2. Leaving all UI work to the last eleven days puts the most visible part of the project at the end
   of the schedule, where slips land.

The glass-box models are small enough to run on a phone for a slice of the catalogue: EASE^R on 500
games is a 500 × 500 Cholesky (about 40 M multiply-adds), PPR forward push from a handful of seeds
touches a few thousand edges, and DPP greedy MAP over 100 candidates is 10 steps.

## Options considered

1. **Static precomputed JSON** (the original FR-22): simplest; replays only.
2. **Live API** (FastAPI on a free host): real model, but a server to keep up, cold starts, and the
   demo dies with the free tier (ADR-0008).
3. **A TypeScript port of the glass-box engine** running in a Web Worker on a real slice of the
   catalogue, with Python as the source of truth and golden tests between them.

## Decision

Option 3, built **alongside** the core rather than after it.

- **Python stays the source of truth** (ADR-0001). The TypeScript engine in `web/src/engine/` is a
  second, independent implementation of the same algorithms: EASE^R, game graph + PPR forward push,
  blend scoring, DPP greedy MAP, exact attributions and live counterfactuals.
- **Golden cross-check.** `whyfinder export demo` writes the slice *and* golden outputs computed by
  Python for fixed histories. Vitest requires the TypeScript engine to reproduce them: scores,
  attributions and Π rows within 1e-9, and identical ranked lists, picks, variety flags and
  counterfactual sets. To make that possible both sides push in the same synchronous rounds (every node
  above its threshold, in ascending node order, contributions summed into a fresh accumulator), fix the
  order of every other sum, and break every tie by game ID.
- **The slice.** The N_demo = 500 games with the most training interactions, with their co-play Gram
  matrix G = XᵀX (train split only), tags, developers, publishers, release year, price, a
  deterministic 2-D layout for the star map, and the model constants that need the whole slice
  (c_B, c_Π). Everything is derived and aggregated; no review text and no user rows are exported.
- **Pairing rule.** Each algorithm lands in Python and TypeScript in the same pull request, with the
  golden test. The demo shows only what has landed; anything planned (iALS, RAG, API) is drawn as
  planned and labelled with its milestone.
- **Hosting** stays static on GitHub Pages (ADR-0008, option 1): no server is needed for the live
  engine.

## Consequences

- Two implementations to keep in step. The golden test fails CI on any drift, which also makes the
  TypeScript engine an extra oracle for the Python one.
- The demo's numbers come from the 500-game slice, not the full 8,000-game model, and the UI says so.
  The full model is evaluated and gated in Python only.
- FR-22 gains an acceptance criterion: the live engine matches the Python goldens.
- The demo work spreads over M0–M4 (see docs/plan/ROADMAP.md), so there is something to show from
  v0.1 onward.
