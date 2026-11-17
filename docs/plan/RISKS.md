# Risks

Reviewed at the end of every milestone. The two biggest: schedule overlap with Bantay, and the
untested assumption about review dates. Both have fallbacks already in the plan.

| # | Risk | Likelihood | Impact | Mitigation | Trigger |
| --- | --- | --- | --- | --- | --- |
| R1 | Time pressure (Bantay, school) | High | High | Each milestone ships alone; cut order: NL queries → graph paths → iALS counterfactuals → live API. Never cut tests or gates | A milestone runs 3 days late |
| R2 | Version 2 reviews lack dates/hours for many rows | Medium | High | Check in M0; leave-last-out fallback (ADR-0002) | > 10% rows without a date |
| R3 | EASE^R memory on a laptop | Medium | Medium | Item cap N_max (ADR-0004); float32 Gram, float64 Cholesky; 10% dev sample | Peak > 70% RAM |
| R4 | PPR precompute too slow | Low | Medium | Push work is O(1/(αε)) per seed; parallelise over seeds; raise ε; cache Π with DVC | > 15 min full build |
| R5 | Blend doesn't match iALS | Medium | Medium | Still publishable: report the accuracy cost of exact explanations; tune γ's and β; add co-play edge weighting | Gap > 0.01 NDCG@10 after tuning |
| R6 | Local LLM fails the checker often | Medium | Medium | Template fallback is always faithful; try a larger local model; tighten the prompt with checker feedback | Claim support < 90% |
| R7 | Embedding the review sample is slow on CPU | Medium | Low | R = 20 reviews per game; batch; run once and version with DVC | > 2 h |
| R8 | Gates fail on noise | Low | Medium | Same users and seeds; non-inferiority margin; `gate:override` only with a written reason | Two false failures in a month |
| R9 | Test-set overfitting via many PRs | Medium | High | Sealed test set, scored only at release | Any PR reading test numbers |
| R10 | Dataset terms or privacy | Low | High | No raw data in Git; hashed usernames; quotes ≤ 25 words; citations | Any request from the authors |
| R11 | Labelled queries biased | Medium | Medium | Written guide; label before seeing outputs; a classmate double-labels 30 (Cohen's κ) | κ < 0.6 |
| R12 | Scope creep | High | Medium | MoSCoW; anything not in 02_REQUIREMENTS needs an issue and a milestone | New idea mid-milestone |
