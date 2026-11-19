# The quality gate fails a worse model

The roadmap asked for proof that the gate (FR-20, ADR-0005) blocks a model that is worse, not only
that it passes good ones. PR [#74](https://github.com/robertgeraldsenasin/whyfinder/pull/74) was
opened for that and closed unmerged.

**The change:** keep only the three largest entries in each row of the blended matrix M
(`blend.top_k_per_row: 500 → 3`), which throws away most of the evidence behind every score.

**What the gate posted** (CI subsample, 3,054 validation users, 2,000 games, 2,000 paired bootstrap
resamples, Holm–Bonferroni over five gated metrics):

| Metric | main | PR #74 | Δ (95% CI) | Gate |
| --- | --- | --- | --- | --- |
| NDCG@10 | 0.0468 | 0.0411 | −0.0057 (−0.0089, −0.0026) | non-inferior ✗ |
| Recall@20 | 0.1287 | 0.0892 | −0.0395 (−0.0485, −0.0306) | non-inferior ✗ |
| ILD@10 | 0.8337 | 0.8580 | +0.0242 (+0.0230, +0.0255) | non-inferior ✓ |
| Additivity | 1.0000 | 1.0000 | | 100% ✓ |
| Counterfactual validity | 1.0000 | 1.0000 | | 100% ✓ |
| Deletion test | 0.9699 | 0.9699 | +0.0000 (−0.0234, +0.0234) | non-inferior ✗ |

The check went red and the PR could not have merged on the gate's say-so. The cheaper model also
looks "more diverse" (ILD up, coverage up from 0.37 to 0.52), which is why the gate never lets
variety buy back lost relevance.

**What it taught us:** the deletion test failed although its mean did not move. With 300 users its
interval (±0.023) was wider than its 0.01 margin, so any model change could fail it on noise. The
sample is now 1,000 users and the margin 0.02 (ADR-0006).
