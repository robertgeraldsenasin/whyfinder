# 07 · Evaluation and quality gates

A pull request can't merge if it makes ranking, explanations or RAG measurably worse. The test is a
**paired bootstrap non-inferiority test** over users: the change must be no worse than `main` by more
than a set margin. (Hasik used SPRT because games are played one at a time; here every test user is
available at once, so a fixed-sample test fits. ADR-0005.)

## Metrics

| Group | Metrics |
| --- | --- |
| Ranking | NDCG@10 (primary), Recall@20, MRR; warm and cold-start users separately |
| Beyond accuracy | Catalogue coverage@10, intra-list diversity (ILD, 1 − mean pairwise tag cosine), average recommendation popularity (ARP) |
| Explanations | 05_EXPLAINABILITY.md table |
| RAG | 06_RAG.md table |
| Systems | Train time, peak memory, p95 latency (release only) |

## Protocol

- **Sealed test set.** PR gates use the **validation** CI subsample. The test set is scored only by
  `release.yml` when a version is tagged; those numbers go to `results/` and the README.
- **Same users, same seeds** for base (main) and head (the PR).
- **Hyperparameters** are tuned on validation only (fixed-budget search, recorded in `params.yaml`).

## Statistics

- Per-user metric arrays for base and head.
- Paired bootstrap of the mean difference: 2,000 user resamples, 95% percentile interval, seed fixed.
- Holm–Bonferroni across the gated metrics in one run.
- **Non-inferiority** (default): pass if the interval's lower end > −δ.
  Proposed δ: 0.005 absolute for NDCG@10 and Recall@20; 1 point for rate metrics.
- **Superiority** (PR label `model:gainer`): pass only if the lower end > 0.

## Gates

| Gate | Rule | Kind | Blocks merge |
| --- | --- | --- | --- |
| Data contracts | All Pandera checks pass | Exact | Yes |
| Oracles | EASE vs dense inverse; PPR vs power iteration; iALS within 2% of `implicit`; HNSW recall ≥ 0.95 | Thresholds | Yes |
| Ranking | NDCG@10 and Recall@20 non-inferior to main | Statistical | Yes |
| Additivity | Contributions sum to scores within 1e-9 | Exact | Yes |
| Counterfactual validity | 100% | Exact | Yes |
| Deletion test | Share of users where attributed removal beats random: non-inferior | Statistical | Yes |
| Diversity | ILD non-inferior | Statistical | Yes |
| RAG claim support | ≥ 95% and non-inferior | Threshold + statistical | Yes |
| Retrieval | Recall@5, nDCG@5 non-inferior | Statistical | Yes |
| Coverage, ARP | Reported with intervals | Report | No |
| Latency | p95 < 150 ms | Threshold | At release |

## PR comment format

```markdown
### Whyfinder quality gate: PASS
| Metric        | main   | this PR | Δ (95% CI)                 | Gate           |
|---------------|--------|---------|----------------------------|----------------|
| NDCG@10       | 0.1234 | 0.1251  | +0.0017 (−0.0009, +0.0043) | non-inferior ✓ |
| ILD           | 0.612  | 0.618   | +0.006 (−0.002, +0.014)    | non-inferior ✓ |
| Claim support | 97.2%  | 97.5%   | +0.3 (−0.4, +1.0)          | ≥ 95% ✓        |
Sample: 5% validation users (n = …), seed 20261117, 2,000 resamples.
```

(Numbers above are placeholders showing the format.)
