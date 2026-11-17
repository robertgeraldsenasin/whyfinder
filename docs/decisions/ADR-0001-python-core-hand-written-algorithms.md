# ADR-0001: Python core, hand-written algorithms, libraries as oracles

- **Status:** Accepted
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

Whyfinder exists to show algorithm work and verifiable explanations. Calling a library for every model would hide the work; writing everything with no reference would risk silent bugs.

## Options considered

1. Library-only (implicit, faiss, rank-bm25)
2. Hand-written only
3. Hand-written core, libraries as test oracles

## Decision

Hand-written implementations of EASE^R, PPR push, blend scoring, DPP, counterfactual search, iALS, BM25 and HNSW in `src/whyfinder/`. Reference libraries (`implicit`, `hnswlib`, `rank-bm25`, dense numpy) appear only in tests and benchmarks. Python 3.12+ for the core; the demo is TypeScript.

## Consequences

More code to maintain; every core module needs an oracle test. Performance work (vectorisation, sparse formats) is part of the job. Interview story: "I wrote it and proved it matches the reference."
