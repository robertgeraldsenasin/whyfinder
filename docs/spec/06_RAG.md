# 06 · Retrieval-augmented explanations

The LLM only **voices** reasons the model already computed; it never decides why. Its output is a
list of claims, each tied to evidence, and a deterministic checker rejects any claim it can't verify.

## Corpus and index (DVC stage `index`)

1. **Sample:** per game, up to R = 20 English reviews from the train period (so evaluation never
   quotes the future), preferring longer reviews; record the sampling seed.
2. **Chunk:** one short review = one chunk; longer ones are split into ~100-word windows with 20 words
   of overlap. Each chunk keeps `chunk_id`, `review_id`, `game_id`, `hours`, `date`.
3. **BM25** (04_ALGORITHMS §A8) over chunks.
4. **Dense:** a small open sentence-embedding model (choice in ADR-0010), L2-normalised vectors in the
   hand-written **HNSW** index (§A9). Embedding runs once offline; vectors are versioned with DVC.

## What runs today (M3, first part)

`src/whyfinder/rag/` holds the retrieval stack, all hand-written: the tokenizer and chunker
(`text.py`), BM25 with the Lucene IDF (`bm25.py`), LSA vectors from a randomized SVD (`lsa.py`,
ADR-0010), the HNSW graph (`hnsw.py`), RRF (`fuse.py`) and the review index that ties them together
(`reviews.py`). The API builds it at start-up over the demo's review export (6,000 quotes of at most
25 words from the train period, `whyfinder export reviews`), so steps 2, 3 and 5 below run now:

- aspects are the tags the pick shares with its top-attributed game, then the review words both
  games' players use;
- each aspect is searched within the pick's reviews; a quote counts only if BM25 matches it, so the
  quote really mentions the aspect;
- the claim cites the chunk and quotes it whole; the checker confirms the chunk belongs to the pick
  and the quote is a verbatim span of at most 25 words, and that the sentence names no game outside
  the pick and the history.

Generation (step 4) is still the template fallback: the sentences are built from E1 and the
retrieved quotes, so `fallback_used` stays true until the LLM lands. The full-corpus DVC `index`
stage and the 150 labelled queries are still to come.

## One explanation, step by step

1. **Inputs:** the pick, its top-5 attributions (E1), the counterfactual set (E2), up to 2 graph paths
   (E3), the variety flag (E4).
2. **Aspects:** tags shared by the pick and its top-attributed games, plus key phrases mined from those
   games' reviews (noun phrases with high PMI against the corpus).
3. **Retrieval:** one query per aspect against the pick's chunks only (metadata filter); BM25 and dense
   rankings fused by RRF (k = 60); keep the top 5 chunks overall.
4. **Generation:** temperature 0, JSON output validated against `claim.schema.json`, at most 3 claims
   and 60 words. Default model: a small open instruct model through **Ollama** (ADR-0009). The model
   name and digest go in every run's metadata.
5. **Checker** (FR-17), deterministic:
   - attribution claims cite a game in the top 5, and any percentage matches its share within 1 point;
   - quotes are verbatim spans (≤ 25 words) of a retrieved chunk;
   - no game is named outside {pick, history, retrieved chunks};
   - counterfactual claims match E2 exactly.
6. **On failure:** regenerate once with the checker's message, then fall back to a template sentence built
   straight from E1–E4 (faithful by construction). Every failure is logged with its reason.

## Claim schema (abridged)

```json
{
  "claims": [
    {"text": "Dead Cells is the biggest driver of this pick (42%).",
     "evidence": [{"type": "attribution", "game_id": "588650", "share": 0.42}]},
    {"text": "Players single out its tight, fast combat.",
     "evidence": [{"type": "review", "chunk_id": "c_8812_0", "quote": "tight, fast combat"}]}
  ]
}
```

## Natural-language queries (FR-18)

"like Hades but co-op, under $20" → anchors (titles matched with BM25 over the catalogue plus a fuzzy
title match; top hit must clear a score threshold) + filters (tag lexicon: `co-op`, price, year). Anchors
become the history x_u with weight 1 each; unresolved words are returned to the user. Rule-based by
default; the LLM is optional and its output goes through the same validation.

## Evaluation

| Measure | How | Pass mark (proposed) |
| --- | --- | --- |
| Claim support | Checker over the CI sample | ≥ 95% before fallback |
| Entailment | Local NLI cross-encoder scores each claim against its evidence | Reported; gated non-inferior |
| Attribution agreement | Kendall τ between the order games are named and attribution order | τ ≥ 0.7 |
| Retrieval | 150 hand-labelled (pick, aspect) queries: Recall@5, nDCG@5 | Gated non-inferior |
| Research ablation | Same prompt without attributions: share of claims that match the model's real top-5 | Reported in the paper |

**Cost and determinism:** generations are cached under hash(prompt, model digest). CI replays the cache
and fails with a clear message on a miss, so CI costs $0 and gives the same result every run.
