# Glossary

| Term | Meaning here |
| --- | --- |
| Attribution | The exact share of a pick's score that comes from one of your games (x_uj · M_ji) |
| Counterfactual | The smallest set of your games whose removal drops a pick from your top 10 |
| EASE^R | Embarrassingly Shallow Autoencoder (Steck 2019): a closed-form item-to-item linear model |
| PPR | Personalized PageRank: a random walk on the game graph that restarts at your games |
| Forward push | A local algorithm that approximates PPR from one seed with bounded error ε·deg(v) |
| Blend (M) | β·EASE + (1−β)·PPR as one sparse item-to-item matrix; the served model |
| DPP | Determinantal point process: a model that prefers sets of items that are both good and different |
| Greedy MAP | The fast DPP selection algorithm (Chen et al. 2018) using incremental Cholesky updates |
| iALS | Implicit alternating least squares (Hu et al. 2008): the latent-factor rival |
| HNSW | Hierarchical Navigable Small World graph: approximate nearest-neighbour index |
| RRF | Reciprocal rank fusion: merges BM25 and dense rankings by 1/(60 + rank) |
| Claim checker | Deterministic code that verifies every sentence the LLM writes against its evidence |
| Non-inferiority | A gate that passes if the change is no worse than main by more than a margin δ |
| Sealed test set | The final split, scored only when a release is tagged |
| Starfall | The design language (ADR-0017): stars = games, picks fall into the sky, lines = reasons, colour = closeness |
