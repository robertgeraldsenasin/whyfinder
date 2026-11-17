# 00 · Vision

> **Whyfinder** — find your next game. Know why.

Whyfinder recommends Steam games and shows, in a form you can check, why it picked each one. Every
reason it gives is the model's actual reason, computed exactly, not a story written after the fact.
CI proves every change keeps it that way.

## The problem

Recommenders are black boxes. When they do explain themselves ("because you played X"), the
explanation is usually a post-hoc guess. LLM-written explanations are worse: fluent, persuasive and
often unrelated to why the model chose the item.

Valve itself has moved toward showing why Steam recommends a game. Whyfinder goes one step further:
its explanations are exact, measurable, and checked by CI.

## The idea in one paragraph

Whyfinder scores games with a **glass-box blend** of two item-to-item models: **EASE^R** (a
closed-form linear autoencoder) and **Personalized PageRank** over a graph of games, tags and
developers. Both are *exactly additive over your history*, so each pick's score splits into "this much
from Hades, this much from Dead Cells" with no approximation, and the smallest set of your games
whose removal drops the pick (a **counterfactual**) can be found exactly. A **DPP re-ranker** keeps the
top 10 varied. An **LLM only voices** those exact reasons, quoting real reviews, and a deterministic
**claim checker** rejects anything it can't verify. A latent-factor model (**iALS**) is kept as the
rival the glass-box blend must match.

## Research question

1. Can a glass-box blend (EASE^R + PPR) match a latent-factor model (iALS) on ranking quality while
   giving exact, verifiable explanations?
2. Does grounding LLM explanations in exact attributions make them faithful, compared with an
   unconstrained LLM given the same picks?

## Why this mix (and why it's uncommon)

| Piece | Why it belongs | Why it isn't the usual student stack |
| --- | --- | --- |
| EASE^R (Steck, WWW 2019) | Strong on sparse implicit data; closed form; item-item weights *are* the explanation | Most projects use matrix factorization or a two-tower model |
| Personalized PageRank (forward push, Andersen–Chung–Lang 2006) | Brings metadata (tags, developers) and co-play into the same additive form; the substrate PRINCE (WSDM 2020) uses for counterfactuals | Graph recommenders are usually GNNs; local push is rarely hand-written |
| Additive blend | Keeps exact attributions *and* exact counterfactuals across both models | Ensembles usually destroy explainability |
| DPP greedy MAP (Chen, Zhang, Zhou, NeurIPS 2018) | Variety without losing relevance; principled, not a heuristic | Diversity is usually skipped or done by genre caps |
| Hand-written HNSW for review retrieval | The RAG layer's index, benchmarked against hnswlib | Usually a vector DB call |
| Claim-checked RAG | LLM may only say what the model computed | Usually free-form generation |
| Bootstrap non-inferiority gates | Statistical CI for ranking, explanation and RAG quality | CI usually stops at unit tests |

## Non-goals (v1)

Steam login or library sync, user accounts, real-traffic A/B tests, LLM fine-tuning, mobile apps,
languages other than English.

## Success

See [01_PRD.md](01_PRD.md) (metrics) and [07_EVALUATION.md](07_EVALUATION.md) (gates).
