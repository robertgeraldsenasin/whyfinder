# Model card: Whyfinder vX.Y.Z

(Template after Mitchell et al., FAT* 2019. `release.yml` fills the numbers from `results/`.)

- **Model:** glass-box blend M = β·EASE^R + (1−β)·PPR (β = …, K_M = …, N_max = …); rival: iALS (f = …).
- **Intended use:** suggesting Steam games to players, with exact reasons. Not for ranking people or content moderation.
- **Data:** UCSD Steam reviews (Version 2), time split T1 = …, T2 = …; k-core = …; users hashed.
- **Metrics (sealed test set, 95% CI):** NDCG@10 …, Recall@20 …, ILD …, coverage …, ARP …
- **Explanation quality:** additivity 100%; counterfactual validity …; deletion test …; minimality gap …
- **RAG:** claim support … (before fallback); entailment …; model … (digest …)
- **Limitations:** English reviews only; popular-game bias in co-play; item cap excludes the long tail from EASE (PPR still reaches it); reviews ≠ preferences.
- **Ethics:** no personal data beyond hashed usernames; quotes ≤ 25 words; dataset cited.
