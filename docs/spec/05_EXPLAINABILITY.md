# 05 · Explainability

Whyfinder shows three kinds of reasons and labels them honestly:

| Kind | Label in the UI | Is it the model's actual reason? |
| --- | --- | --- |
| **Attribution** | "Because you played …" with exact shares | Yes, exact |
| **Counterfactual** | "Without Dead Cells in your list, this pick drops out" | Yes, verified by re-running the pipeline |
| **Graph path** | "Related by: same developer · shares the rare tag *Metroidvania*" | No: a related fact, shown as "related by", never "because" |
| **Variety flag** | "Kept for variety" | Yes: DPP chose it over a higher-scored, more similar game |

## E1 · Exact attributions

For the blend (04_ALGORITHMS §A5) the score is a sum over the user's own games:

$$s_{ui} = \sum_{j \in H(u)} \underbrace{x_{uj}\, M_{ji}}_{a_{ji}} = \beta \sum_j \frac{x_{uj} B_{ji}}{c_B} + (1-\beta) \sum_j \frac{x_{uj}\Pi_{ji}}{c_\Pi}$$

So each contribution a_ji further splits into an EASE part (co-play pattern) and a PPR part (shared
tags, developer, co-play walks). The UI shows the share a_ji / s_ui; negative contributions are shown
as negative ("pulls this down").

**iALS (rival):** Hu, Koren and Volinsky show the same kind of decomposition,
ŷ_ui = Σ_j s^u_ij c_uj with s^u_ij = y_iᵀ W^u y_j, W^u = (YᵀC^uY + λI)⁻¹. It's exact too, but
W^u depends on the whole history, so removing a game changes every other game's weight: that's why
iALS counterfactuals need search and the blend's don't.

## E2 · Counterfactuals

Definition (after PRINCE, WSDM 2020): the smallest set of the user's own games whose removal changes
the recommendation. Methods and guarantees: 04_ALGORITHMS §A7. The UI states the guarantee it has
("smallest possible" offline, "no game can be removed from this set" live).

## E3 · Graph paths

For a pick i and its top-attributed history game j, find paths of length ≤ 3 in the game graph between
them (BFS with a visit cap), ranked by the rarity of the shared node (IDF for tags; 1/degree for
developers). Show at most 2.

## E4 · Variety flag

A pick is "kept for variety" when it is in the DPP top 10 but not in the relevance-only top 10. Its
attribution is still shown.

## How explanations are measured (CI)

| Check | Question | Pass mark (proposed, ADR-0006) |
| --- | --- | --- |
| Additivity | Do contributions sum to the score? | Within 1e-9, 100% of picks |
| Deletion test | Does removing the top-3 attributed games lower the pick's score more than removing 3 random games of the same user? | ≥ 95% of test users; deletion-curve AUC reported |
| Counterfactual validity | Does removing the set remove the pick from the final top 10? | 100% |
| Minimality gap | Greedy size − exact size | Mean reported; gated non-inferior to main |
| Stability | Top-3 attributed games across 3 retrain seeds (iALS only; the blend is deterministic) | Mean Jaccard reported |
| Randomisation sanity check (Adebayo et al., NeurIPS 2018) | Do attributions from a model with shuffled item IDs differ? | Rank correlation with the real model near 0 |
| Path validity | Does every shown path exist in the graph? | 100% |
| Glass box vs black box | Explanation fidelity and accuracy, blend vs iALS | Reported in the paper, not gated |
