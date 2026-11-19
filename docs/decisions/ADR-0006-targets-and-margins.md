# ADR-0006: Success targets and gate margins

- **Status:** Accepted (baselines recorded 2026-11-20)
- **Date:** 2026-11-17, fixed 2026-11-20
- **Deciders:** Robert Gerald Senasin

## Context

Targets set before seeing baselines are guesses. This record said it would confirm or adjust each
target once, after the M1 baselines. Those baselines now exist, from validation users only (the test
split stays sealed until the release).

**Full data, validation** (5,000 users, 8,000 games; `results/validation/tune-2026-11-19.json`):

| Model (best setting in its grid) | NDCG@10 |
| --- | --- |
| Blend, β = 0.25 | 0.0441 |
| EASE^R, λ = 500 | 0.0436 |
| Whyfinder (blend + DPP, θ = 1) | 0.0413, ILD@10 0.826 |
| Item-kNN, shrinkage 50 | 0.0357 |
| iALS, reg 0.1, α 5 | 0.0294 |
| PPR alone (β = 0) | 0.0319 |

**CI subsample, validation** (3,054 users, 2,000 games; the gate's sample, before tuning, β = 0.5,
θ = 2): blend NDCG@10 0.0484 / Recall@20 0.1287 / ILD@10 0.8120; Whyfinder 0.0468 / 0.1287 /
0.8337; popularity 0.0450 / 0.0995 / 0.7677; iALS 0.0312 / 0.0790. Explanation checks on 300
users: additivity 1.0, counterfactual validity 1.0, deletion 0.970, minimality gap 0.018,
shuffled-model rank correlation 0.008.

## Options considered

1. Keep every proposed target as written.
2. Confirm the targets the baselines support, and change only those the baselines show to be
   unmeasurable or meaningless, saying why.

## Decision

Option 2. Each target below is now fixed; changing one again needs a new ADR.

| Area | Target | Change |
| --- | --- | --- |
| Ranking | Blend non-inferior to iALS on NDCG@10 (δ = 0.005); Whyfinder beats popularity with p < 0.05 on NDCG@10 and Recall@20 | Confirmed. Validation clears the first by a wide margin; on the CI subsample Recall@20 is far ahead of popularity and NDCG@10 only slightly, so the second may fail on NDCG@10, and the release will say so if it does |
| Explanation fidelity | Deletion test ≥ 95% of users | Confirmed (0.970) |
| Diversity | DPP closes ≥ 10% of the ILD@10 headroom left by the relevance-only list, (ILD_dpp − ILD_blend) / (1 − ILD_blend), at an NDCG@10 cost ≤ 0.005 | Changed from "ILD up ≥ 15%". Relevance-only lists already score 0.81, so +15% would need 0.93, a level no setting in the grid comes near without wrecking relevance. Measured as a share of the headroom, the CI subsample gives 11.5% at θ = 2 |
| RAG faithfulness | ≥ 95% of claims verified before fallback | Unchanged (measured from M3) |
| Engineering | CI green; core line coverage ≥ 85%; axe 0 violations | Unchanged |

**Gate margins.** δ = 0.005 for NDCG@10 and Recall@20 and 0.01 for ILD@10 are confirmed: a
deliberately worse model (PR #74, `docs/evidence/gate-proof.md`) lost 0.006 NDCG@10 and 0.040
Recall@20 and failed. The explanation sample grows from 300 to 1,000 users and the deletion margin
from 0.01 to 0.02: at 300 users the deletion test's 95% interval was ±0.023, so it failed PR #74
although its mean had not moved. The minimality-gap margin stays 0.1.

**Tuned values** (in `params.yaml`): λ = 500, β = 0.25, θ = 1.0, item-kNN shrinkage 50, iALS
reg 0.1 and α 5. θ = 1.0 is the edge of its grid: every θ tried stayed within the NDCG budget, and
the gate's tuning rule takes the most variety within it.

## Consequences

- The release reports each target as met or not met against these values, including any miss.
- A model PR now fails the gate on real losses, not on the deletion test's sampling noise.
- The diversity target is stated in a form that still means something when lists are already varied.
