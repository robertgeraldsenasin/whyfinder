# ADR-0010: Retrieval: hybrid BM25 + dense on our own HNSW, merged by RRF

- **Status:** Proposed (embedding model chosen in M3)
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

Review text is noisy; keyword and semantic matches fail in different ways.

## Options considered

1. BM25 only
2. Dense only
3. Hybrid with RRF
4. A hosted vector database

## Decision

BM25 (hand-written) plus dense retrieval on the hand-written HNSW index, fused with reciprocal rank fusion (k = 60), filtered to the pick's reviews. Choose a small open sentence-embedding model in M3 (CPU-friendly) and record it here.

## Consequences

No external service; retrieval quality is gated on 150 labelled queries.
