# ADR-0010: Retrieval: hybrid BM25 + dense on our own HNSW, merged by RRF

- **Status:** Accepted (dense side settled 2026-11-20; corpus settled 2026-11-28)
- **Date:** 2026-11-17, amended 2026-11-20 and 2026-11-28
- **Deciders:** Robert Gerald Senasin

## Context

Review text is noisy; keyword and semantic matches fail in different ways. This record left the
embedding model open until M3. Two things shaped the choice: the API image and CI must stay free and
CPU-only, and every number in the project must be reproducible from the repository and a seed.

## Options considered

1. BM25 only
2. Dense only
3. Hybrid with RRF
4. A hosted vector database

For the dense side:

- **A small sentence-embedding model** (for example all-MiniLM-L6-v2 through sentence-transformers or
  ONNX Runtime). Better at paraphrase. Adds a model download, a 100+ MB runtime dependency and a
  second source of nondeterminism (thread counts, library versions) to CI and the image.
- **Latent semantic analysis**: TF-IDF and a truncated SVD, written here (randomized range finder,
  Halko et al. 2011). Weaker semantics, but no download, no new dependency, fit in under a second
  on 6,000 quotes, and fully determined by the corpus and the seed.

## Decision

Option 3. BM25 (hand-written, Lucene IDF) plus dense retrieval on the hand-written HNSW index, fused
by reciprocal rank fusion (k = 60), filtered to the pick's reviews when explaining a pick.

The dense side is LSA with 128 dimensions (`rag.lsa` in params.yaml). The HNSW graph uses M = 16,
efConstruction = 200 and efSearch = 64 as specified. On the demo's 6,000 review quotes the
pure-Python build takes about 20 s; recall@10 against exact search is ≥ 0.95 in the tests.

A sentence-embedding model can replace LSA later behind the same `embed` call; the switch needs a
new ADR and the retrieval numbers to hold or improve.

**The corpus** (amended 2026-11-28). 06_RAG planned a DVC `index` stage over up to 20 reviews for
every game in the model. That index was for an API serving the full model; since ADR-0019 the API
serves the demo slice, and the review export already covers every game in it. A full-corpus index
would be built and versioned for nothing to read, so the stage is dropped and the served corpus
stays the review export (6,000 quotes, 12 per game). What the stage would have shown, that the
hand-written graph holds up at scale, is measured instead: on 99,693 sentences from the full corpus
it reaches recall@10 of 0.963 at efSearch 64 against hnswlib's 0.957, building in five minutes
(`docs/evidence/hnsw-bench.md`). If the API ever serves the full model, the stage comes back with
it.

## Consequences

- No external service, no model download, the same vectors on every machine.
- Paraphrases with no shared words are found less often than a neural encoder would find them;
  BM25 carries exact-term queries, which is what aspect queries mostly are.
- Retrieval quality is to be gated on 150 hand-labelled queries. The sheet, the guide and the
  scorer are in (`docs/labelling/retrieval.md`); until the grades exist, the tests cover
  correctness (BM25 against a reference, HNSW recall against exact search) and the claim checker
  refuses any quote that is not verbatim.
