# Model card: Whyfinder v0.2.0

Format after Mitchell et al., FAT* 2019. Every number below comes from `results/` (the sealed test
set, scored once by `release.yml` for v0.2.0) or from `results/validation/` (validation users only).

## Model

- **Recommender:** a glass-box blend M = β·B/c_B + (1 − β)·Π/c_Π of EASE^R (λ = 500) and
  Personalized PageRank over a game–tag–developer–publisher–co-play graph, β = 0.25, each row of M
  kept to its 500 largest entries, EASE capped at the 8,000 most-played games (ADR-0004). The top 10
  are re-ranked by a DPP (θ = 1, 100 candidates).
- **Rival:** iALS with 64 factors, reg 0.1, α 5.
- **Baselines:** popularity, item-kNN (shrinkage 50), EASE alone, PPR alone.
- **Settings** were tuned on validation users only (`results/validation/tune-2026-11-19.json`).

## Intended use

Suggesting Steam games to a player from games they liked, each pick with its exact reasons: how
much each liked game contributed, the smallest set of liked games whose removal drops the pick, and
the graph paths behind it. Not for ranking people, moderating content or judging game quality.

## Data

UCSD Steam datasets (Version 2: reviews and play time). 6.9 M interactions from 2.57 M users on
15,474 games; a 5-core leaves 3.48 M interactions, 281,210 users and 11,961 games. Global time
split: train before 2017-05-31, validation to 2017-10-01, test after. Test users need train
history and test games must be known, which drops 34,582 test rows without history and 87,735 on
unseen games. Usernames are hashed; no other personal data is used. Cold-start users (at most four
train games) are scored separately; that report is attached to the v0.2.0 release.

## Metrics (sealed test set, 20,000 users, 95% bootstrap intervals)

| Model | NDCG@10 | Recall@20 | MRR | ILD@10 | Coverage@10 |
| --- | --- | --- | --- | --- | --- |
| **Whyfinder** (blend + DPP) | 0.0447 [0.0428, 0.0467] | 0.1194 [0.1155, 0.1235] | 0.0600 | 0.828 | 0.299 |
| Blend, no re-ranking | 0.0456 [0.0437, 0.0477] | 0.1196 [0.1157, 0.1236] | 0.0605 | 0.777 | 0.298 |
| EASE^R | 0.0452 | 0.1189 | 0.0600 | 0.782 | 0.221 |
| Popularity | 0.0454 [0.0433, 0.0474] | 0.1075 [0.1038, 0.1115] | 0.0636 | 0.738 | 0.007 |
| Item-kNN | 0.0420 | 0.0976 | 0.0582 | 0.776 | 0.241 |
| iALS | 0.0321 | 0.0826 | 0.0420 | 0.790 | 0.126 |
| PPR | 0.0313 | 0.0771 | 0.0444 | 0.728 | 0.621 |

Against the targets fixed in ADR-0006 before the test set was read:

- **Met:** the blend is non-inferior to iALS on NDCG@10 (+0.0135); Whyfinder beats popularity on
  Recall@20 (+0.0119, p < 0.001); the DPP closes 22.7% of the ILD headroom (0.777 → 0.828) at an
  NDCG@10 cost of 0.0010.
- **Not met:** Whyfinder does not beat popularity on NDCG@10 (0.0447 vs 0.0454, p = 0.78).
  Popularity is strong at the very top of a time-split list, where the games everyone starts
  playing next dominate; it is also the narrowest model by far, covering 0.7% of the catalogue in
  its top 10 against 30% for Whyfinder.

## Explanation quality (sealed test set)

Additivity 100% (contributions sum to the score within 1e-9); counterfactual validity 100% (every
removal set, re-run through the full pipeline, drops the pick); deletion test 96.8% of users
(removing the top-attributed games lowers the score more than removing random ones). On validation
the greedy counterfactual is on average 0.018 games larger than the exact minimum, and a
shuffled-model check correlates at 0.008, so the attributions track this model and not a generic
popularity signal.

## Retrieval and generated words

Review retrieval (BM25, LSA vectors in a hand-written HNSW, RRF) runs over 6,000 review quotes from
the train period. HNSW recall@10 against exact search is 0.999 at efSearch 64 on those vectors
(`docs/evidence/hnsw-bench.md`). Explanations served by v0.2.0 are template sentences built from the
exact attributions plus verbatim quotes, every one checked; LLM-written sentences are evaluated
separately (06_RAG) and are not part of this release.

## Limitations

- English reviews only; reviews are not the same as preferences, and play time is a noisy signal.
- Co-play edges and popularity favour games many people already play; the item cap keeps the long
  tail out of EASE (PPR still reaches it).
- The time split ends in 2017; the catalogue and tastes have moved since.
- Popularity matches Whyfinder at the very top of the list (see above).

## Ethics

No personal data beyond hashed usernames. Quotes are at most 25 words, attributed to no one. The
dataset is cited (Kang and McAuley, ICDM 2018; Wan and McAuley, RecSys 2018; Pathak, Gupta and
McAuley, SIGIR 2017).
