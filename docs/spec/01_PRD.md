# 01 · Product requirements

Version 1 does one job: **find my next game and tell me honestly why.**

## Personas

| Persona | Goal | What Whyfinder must give them |
| --- | --- | --- |
| Mika, player with ~20 games | Something to play this weekend | Top 10 with reasons she can check; filters (tag, price, co-op) |
| New visitor, no history | Try it without an account | Pick 3–5 liked games, get picks immediately (no fold-in needed: the models are item-based) |
| Reviewer (recruiter, professor, engineer) | Judge the engineering in 10 minutes | Live demo, README numbers, visible CI gates, ADRs |
| Gerald, maintainer | Change models without fear | Gates that block regressions; one-command reproduction |

## User stories (MoSCoW)

| ID | Story | Priority |
| --- | --- | --- |
| US-01 | I pick games I like and get a ranked top 10. | Must |
| US-02 | For each pick I see which of my games drove it, with exact shares. | Must |
| US-03 | I see a counterfactual: "without Dead Cells in your list, this pick drops out." | Must |
| US-04 | Every sentence of a written explanation links to its evidence (an attribution or a review quote). | Must |
| US-05 | My top 10 isn't ten copies of the same game; picks kept for variety say so. | Should |
| US-06 | I can ask in words: "like Hades but co-op". | Should |
| US-07 | I can filter by tag, price and release year. | Should |
| US-08 | I see the picks as a star map: my games, the picks, and the lines of reasoning between them. | Should |
| US-09 | As maintainer, every PR gets a quality report: deltas vs main with confidence intervals. | Must |
| US-10 | As a reviewer, `make reproduce` rebuilds every README number from raw data. | Must |

## Success metrics (proposed; fixed in ADR-0006 after M1 baselines)

| Area | Target | Measured by |
| --- | --- | --- |
| Ranking | Blend non-inferior to iALS on NDCG@10 (margin 0.005); beats popularity with p < 0.05 | Paired bootstrap, time-split test set |
| Attributions | Sum to the score within 1e-9 (exact) | Property test + CI |
| Counterfactuals | 100% valid; exact minimal for sets up to 3 | Re-scoring the full pipeline |
| Explanation fidelity | Removing top-3 attributed games drops the score more than 3 random ones for ≥ 95% of users | Deletion test |
| Diversity | Intra-list diversity up ≥ 15% vs no re-ranking, NDCG@10 loss ≤ 0.005 | Paired bootstrap |
| RAG faithfulness | ≥ 95% of claims verified before fallback | Claim checker |
| Serving | p95 < 150 ms for top 10 without the LLM | Locust at release |
| Engineering | CI green; core line coverage ≥ 85%; axe 0 violations in the demo | GitHub Actions |
