# 04 · Algorithms

Every core algorithm is written by hand and checked against an independent oracle (a reference
library, a dense brute-force computation, or a mathematical identity). Libraries are test oracles,
never the implementation (ADR-0001).

Notation: m users, n games, N observed interactions, H(u) the history of user u, x_u ∈ ℝⁿ the
confidence weights of u's history (0 elsewhere), k the list length (10).

## Pipeline at a glance

```
history x_u ──► scores s_u = x_u · M ──► drop owned, apply filters ──► top 100 ──► DPP ──► top 10
                      ▲                                                                   │
        M = β·B/c_B + (1−β)·Π/c_Π                                        attributions, counterfactuals,
        (B: EASE^R, Π: Personalized PageRank)                            paths, grounded text
```

## A1 · Baselines

- **Popularity:** games ranked by summed confidence in train.
- **Item-kNN:** sim(a, b) = a·b / (‖a‖‖b‖ + s) on train columns, shrinkage s tuned; keep top 100 per
  item. Oracle: dense computation on 1,000 items.

## A2 · EASE^R (Steck, WWW 2019)

A linear autoencoder with a zero-diagonal constraint, solved in closed form. With X the binary train
matrix (m × n) and G = XᵀX:

$$P = (G + \lambda I)^{-1}, \qquad B_{ij} = -\frac{P_{ij}}{P_{jj}}\ (i \ne j), \qquad B_{jj} = 0$$

- **Cost:** O(n³) time for the inverse, O(n²) memory. With the item cap N_max = 8,000 (ADR-0004) the
  float64 inverse needs ~0.5 GB; compute G in float32 from a sparse X, invert in float64 with
  Cholesky (G + λI is symmetric positive definite).
- **Scoring:** s_u = x_u B (confidence-weighted history; binary as an ablation).
- **Oracle:** `numpy.linalg.inv` on a 300-item fixture to 1e-8; property test B_jj = 0.

## A3 · iALS rival (Hu, Koren, Volinsky, ICDM 2008)

Kept so the glass-box blend has a strong latent-factor model to match.

$$L = \sum_{u,i} c_{ui}\,(p_{ui} - x_u^{\top} y_i)^2 + \lambda\Big(\sum_u \lVert x_u\rVert^2 + \sum_i \lVert y_i\rVert^2\Big)$$

$$x_u = \big(Y^{\top}Y + Y^{\top}(C^u - I)\,Y + \lambda I\big)^{-1} Y^{\top} C^u p(u)$$

Per sweep O(f²N + f³(m + n)); Cholesky and conjugate-gradient solvers. Oracle: the `implicit`
library at equal α, λ, f and seed (NDCG@10 within 2%).

## A4 · Game graph and Personalized PageRank

**Graph.** Nodes: games, tags, developers, publishers. Undirected weighted edges:

| Edge | Weight | Limit |
| --- | --- | --- |
| game–tag | γ_tag · idf(tag) | top 20 tags per game |
| game–developer | γ_dev | all |
| game–publisher | γ_pub | all |
| game–game (co-play) | γ_co · cosine on train columns | top 20 per game |

The γ's are tuned on validation. P = D⁻¹W is the random-walk matrix.

**PPR from one seed game g** (restart probability α, default 0.15):

$$\pi_g = \alpha\, e_g + (1-\alpha)\, \pi_g P$$

**Forward push** (Andersen, Chung, Lang, FOCS 2006). Keep an estimate p and a residual r, starting
with r = e_g. While some node v has r(v) > ε·deg(v): add α·r(v) to p(v), spread (1−α)·r(v) to v's
neighbours in proportion to edge weight, set r(v) = 0. Guarantee: |π_g(v) − p(v)| ≤ ε·deg(v).
Work is O(1/(αε)) per seed, independent of graph size.

**Item-item matrix Π.** Row g keeps the top M_Π = 200 game entries of p (the seed itself excluded).
Precomputed offline for all n games: embarrassingly parallel, deterministic order.

**Why PPR is additive.** PPR is linear in the restart vector: π_{Σ w_j e_j} = Σ w_j π_{e_j}. So
s_u = x_u Π is exactly the PPR score of a walk restarting at u's games with weights x_u (for the stored,
truncated Π). This is the substrate PRINCE (Ghazimatin et al., WSDM 2020) uses for counterfactuals.

**Oracles:** power iteration to 1e-12 on a 2,000-node fixture (|π − p| ≤ ε·deg); truncation loss
(mass outside top M_Π) reported per run.

## A5 · Glass-box blend

$$M = \beta\,\frac{B}{c_B} + (1-\beta)\,\frac{\Pi}{c_\Pi}, \qquad \operatorname{diag}(M) = 0, \qquad s_u = x_u M$$

- c_B, c_Π: global constants (99th percentile of |non-zero| entries), so scales are comparable and
  additivity survives (a per-user normalisation would break it).
- β ∈ [0, 1] tuned on validation NDCG@10. β = 1 is pure EASE, β = 0 pure PPR: both ablations are
  reported.
- M is stored as CSR with the top K_M = 500 entries per row. **The served model is the stored M**, so
  every attribution is exact with respect to what is served; the cost of truncation is reported as an
  NDCG delta against the dense blend.
- Scoring a user: O(|H(u)| · K_M), then exclude owned games, apply filters, take the top 100.

## A6 · DPP re-ranking (Chen, Zhang, Zhou, NeurIPS 2018)

Pick 10 of the top 100 candidates that are both relevant and varied, by greedy MAP inference on a
determinantal point process with kernel

$$L = \operatorname{Diag}(q)\, S\, \operatorname{Diag}(q), \qquad q_i = \exp(\theta\, \hat s_i), \qquad S_{ij} = f_i^{\top} f_j$$

where ŝ is the blend score rescaled to [0, 1] within the candidate set and f_i is the L2-normalised
TF-IDF tag-and-genre vector of game i (so S is positive semidefinite).

**Greedy MAP with incremental Cholesky:** keep c_i (growing vectors) and d_i² = L_ii. Each step
choose j = argmax d_i²; for every remaining i set e_i = (L_ji − ⟨c_j, c_i⟩)/d_j, append e_i to c_i,
d_i² ← d_i² − e_i². Cost O(N k²) for N = 100, k = 10. Ties break by game ID (deterministic).

θ trades relevance for variety: tuned so NDCG@10 drops by ≤ 0.005 while intra-list diversity rises.

**"Kept for variety" flag:** a pick in the DPP top 10 that is not in the relevance-only top 10.

**Oracle:** brute-force log-det argmax over all 10-subsets of 12-candidate fixtures (greedy must match
the brute-force first pick and stay within the known approximation on the rest; recorded, not
asserted as optimal).

## A7 · Counterfactual search

Find the smallest S ⊆ H(u) such that pick i is not in the full pipeline's output for history H(u) \ S.

Because s_u is linear in x_u, removing S changes **every** candidate's score exactly:
s'_u = s_u − Σ_{j∈S} x_uj M_j·. No refitting is needed. The pipeline (filters, top 100, DPP) is
re-run on s'_u, so validity is checked end to end.

| Mode | Method | Guarantee | Cost |
| --- | --- | --- | --- |
| Live (`/explain`) | Greedy: remove games in order of contribution to i, re-run until i drops; then prune any game whose return keeps i out | Valid and irreducible (no game can be dropped from S) | O(|H|) pipeline runs, ~1 ms each |
| Offline (eval) | Enumerate subsets of size 1, 2, 3 of the 20 largest contributors | Exact minimum among those; exact overall when |H| ≤ 20 | ≤ 1,350 runs |
| iALS rival | Greedy with Sherman–Morrison rank-one downdates of W^u | Valid, irreducible | O(|H|·f²) |

The minimality gap (greedy size − exact size) is a tracked metric.

## A8 · BM25 (Robertson; Lucene IDF variant)

$$\text{idf}(t) = \ln\Big(1 + \frac{N - df_t + 0.5}{df_t + 0.5}\Big), \qquad \text{score}(q,d) = \sum_{t\in q} \text{idf}(t)\,\frac{tf_{t,d}(k_1+1)}{tf_{t,d} + k_1\,(1 - b + b\,|d|/\overline{|d|})}$$

k₁ = 1.2, b = 0.75. Sparse matrices; tokeniser: lowercase, Unicode word split, English stop words.
Oracle: `rank-bm25` on a fixture.

## A9 · HNSW (Malkov & Yashunin)

Layered proximity graph over L2-normalised review-chunk embeddings (inner product). M = 16
(M₀ = 32 at layer 0), efConstruction = 200, efSearch = 64, level ~ ⌊−ln(U)·m_L⌋ with m_L = 1/ln M,
neighbour-selection heuristic, seeded RNG so builds are reproducible. Oracles: exact top-k
(recall@10 ≥ 0.95); benchmark: hnswlib (build time, QPS, recall curve over efSearch).

## A10 · Reciprocal rank fusion

score(d) = Σ_r 1 / (60 + rank_r(d)) over the BM25 and dense rankings.

## Complexity summary

| Algorithm | Offline | Per request | Hand-written | Oracle |
| --- | --- | --- | --- | --- |
| Item-kNN | O(N · avg history) | O(|H| · 100) | Yes | Dense |
| EASE^R | O(n³) (n ≤ N_max) | via M | Yes | numpy inverse |
| PPR push | O(n / (αε)) total | via M | Yes | Power iteration |
| Blend scoring | O(n · K_M) build | O(|H| · K_M) | Yes | Dense blend |
| DPP greedy MAP | — | O(100 · 10²) | Yes | Brute force (12 items) |
| Counterfactual (live) | — | O(|H|) pipeline runs | Yes | Exact enumeration |
| iALS | O(f²N + f³(m+n)) per sweep | O(nf) | Yes | `implicit` |
| BM25 | O(total tokens) | O(|q| · postings) | Yes | rank-bm25 |
| HNSW | ~O(c log c) for c chunks | ~O(log c) | Yes | Exact, hnswlib |

## References

- Steck, H. Embarrassingly Shallow Autoencoders for Sparse Data. WWW 2019.
- Hu, Y., Koren, Y., Volinsky, C. Collaborative Filtering for Implicit Feedback Datasets. ICDM 2008.
- Andersen, R., Chung, F., Lang, K. Local Graph Partitioning using PageRank Vectors. FOCS 2006.
- Ghazimatin, A., Balalau, O., Saha Roy, R., Weikum, G. PRINCE: Provider-side Interpretability with
  Counterfactual Explanations in Recommender Systems. WSDM 2020.
- Chen, L., Zhang, G., Zhou, H. Fast Greedy MAP Inference for Determinantal Point Process to Improve
  Recommendation Diversity. NeurIPS 2018.
- Malkov, Y., Yashunin, D. Efficient and Robust Approximate Nearest Neighbor Search Using Hierarchical
  Navigable Small World Graphs. IEEE TPAMI 2020.
- Cormack, G., Clarke, C., Büttcher, S. Reciprocal Rank Fusion. SIGIR 2009.
