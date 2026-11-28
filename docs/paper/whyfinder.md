# Exact reasons, honestly measured: an additive hybrid recommender for Steam games

*Robert Gerald Senasin, FEU Institute of Technology. Draft, November 2026.*

## Abstract

Explanations in recommender systems are usually produced after the fact by a second model, so
nothing guarantees they describe what the recommender actually did. We build a recommender whose
explanations are its arithmetic. Scores come from a blend of EASE^R and Personalized PageRank, both
additive over the user's history, so each liked game's share of a score is exact. On top of that we
compute counterfactual sets by re-running the full pipeline, re-rank for variety with a
determinantal point process, retrieve review quotes with a hand-written hybrid index, and check
every generated sentence against the computed facts. On a time split of the UCSD Steam data with a
test set read once, the blend reaches NDCG@10 of 0.0447 and Recall@20 of 0.1194, beating iALS by
0.0135 NDCG@10 and popularity by 0.0119 Recall@20, while covering 30% of the catalogue in its top
ten against popularity's 0.7%. It does not beat popularity on NDCG@10 (Δ −0.0007, p = 0.78), a
target we set before reading the test set and report as missed. Attributions sum to the score in
100% of checks and counterfactual sets are valid in 100%. Small local language models asked to voice
the facts passed the checker within two tries at most 32% of the time when free; pinning each
sentence to one fact during decoding raised a 3B model to 99.4% of claims kept, though half of
its sentences then only restate the fact. Freeing the wording again ends the copying, but a judge
model, calibrated on the template sentences, finds 8% to 20% of the freed sentences contradict the
facts, against 4% of the template's.

## 1. Introduction

A player who is told "you might like Team Fortress 2 because you played Portal 2" should be able to
ask how much Portal 2 mattered, and whether the pick would survive without it. Most deployed
explanation methods cannot answer either question exactly: they approximate a black-box model
locally, or they generate text from features the model may not have used.

We take the opposite route and restrict the recommender to models whose scores decompose over the
user's history. That choice costs some modelling freedom and buys three things: exact attributions,
counterfactuals that can be verified by re-running the system, and explanations that a program can
check. The contributions of this project are:

1. a blended recommender (EASE^R and Personalized PageRank) with exact per-game attributions,
   greedy-then-pruned counterfactual sets, and DPP re-ranking that reports which picks it kept for
   variety;
2. an evaluation protocol with targets fixed before the test set is read, a per-change quality gate
   (paired bootstrap non-inferiority with Holm correction) and a demonstration that the gate rejects
   a degraded model;
3. a grounded explanation layer: hand-written BM25, LSA and HNSW retrieval over reviews, a claim
   schema, and a deterministic checker that every sentence must pass;
4. a measurement of how often small local language models produce sentences that survive that
   checker, free and with each sentence pinned to a fact while decoding.

## 2. Model

**Data.** Steam interactions with play time (Kang and McAuley 2018; Wan and McAuley 2018; Pathak et
al. 2017): 6.9 M interactions from 2.57 M users on 15,474 games, reduced by a 5-core to 3.48 M
interactions, 281,210 users and 11,961 games. Play time h becomes a confidence weight
w = 1 + α·log(1 + h/ε) with α = ε = 1.

**EASE^R** (Steck 2019) learns an item-to-item matrix B = I − P·diag(1/diag(P)), P = (XᵀX + λI)⁻¹,
with a zero diagonal, λ = 500, over the 8,000 most-played games.

**Personalized PageRank** runs on a graph of games, tags, developers, publishers and co-play edges,
with forward push (Andersen et al. 2006; restart 0.15, ε = 10⁻⁶). Row j of Π holds the PPR mass
reaching each game from game j.

**Blend.** M = β·B/c_B + (1 − β)·Π/c_Π, where c_B and c_Π put both parts on one scale, β = 0.25,
and each row keeps its 500 largest entries. The score of game i for a user with weighted history
x is s_i = Σ_j x_j M_ji, so the contribution of liked game j is x_j M_ji, split exactly into an
EASE part and a graph part. Ties are broken by game ID everywhere.

**Re-ranking.** The top 100 by score are re-ranked with the greedy DPP MAP of Chen et al. (2018)
over tag similarity, with quality exponent θ = 1. A pick that the DPP promoted past a more relevant
game is flagged as kept for variety.

**Counterfactuals.** Following PRINCE (Ghazimatin et al. 2020), the explanation includes the
smallest set of liked games whose removal drops the pick from the top ten. Live, we remove games in
attribution order until the pick drops, re-running the whole pipeline (re-ranking included) each
time, and then prune any game whose return does not bring the pick back. The result is valid and
irreducible. Offline, an exact search over sets of up to three games measures how much larger the
greedy set is.

**Rival.** iALS (Hu et al. 2008) with 64 factors, regularisation 0.1 and α = 5, tuned on
validation, as Rendle et al. (2022) advise for this baseline. Its counterfactuals use
Sherman–Morrison downdates of the folded-in user's inverse, which match a fresh solve to 10⁻⁸ and
take about 17 µs against 97 µs for a solve that reuses YᵀY.

All settings were tuned on validation users only.

## 3. Evaluation protocol

The split is global by time: training before 31 May 2017, validation to 1 October 2017, test after.
Test users must have training history, and test games must be known. We report NDCG@10, Recall@20,
MRR, intra-list diversity over tags (ILD@10) and catalogue coverage@10 on 20,000 test users, each
with a 95% bootstrap interval over users.

The test split is read by one workflow, once per release. Targets were written before any test
number existed and adjusted once, after validation baselines, in a recorded decision. Every change
to the model goes through a gate that compares it with the main branch on a fixed validation
subsample (3,054 users, 2,000 games): a paired bootstrap non-inferiority test on NDCG@10, Recall@20
and ILD@10 and on two explanation checks, with Holm–Bonferroni correction (Holm 1979). To show the
gate works, we submitted a change that kept only three entries per row of M. The gate failed it
(Recall@20 0.1287 → 0.0892), and the exercise exposed one check whose sample was too small for its
margin, which we then fixed.

**Explanation checks.** Additivity: the contributions sum to the score within 10⁻⁹. Counterfactual
validity: removing the set and re-running the pipeline drops the pick. Deletion (after Petsiuk et
al. 2018): removing the three most-attributed games pushes the pick further down than removing
three random liked games. Minimality gap: greedy size minus exact size. Model-randomisation sanity
check (Adebayo et al. 2018): the Spearman correlation between attributions under M and under M with
shuffled rows, which should be near zero.

## 4. Results

**Ranking (test set, 20,000 users).**

| Model | NDCG@10 | Recall@20 | MRR | ILD@10 | Coverage@10 |
| --- | --- | --- | --- | --- | --- |
| Whyfinder (blend + DPP) | 0.0447 | 0.1194 | 0.0600 | 0.828 | 0.299 |
| Blend | 0.0456 | 0.1196 | 0.0605 | 0.777 | 0.298 |
| EASE^R | 0.0452 | 0.1189 | 0.0600 | 0.782 | 0.221 |
| Popularity | 0.0454 | 0.1075 | 0.0636 | 0.738 | 0.007 |
| Item-kNN | 0.0420 | 0.0976 | 0.0582 | 0.776 | 0.241 |
| iALS | 0.0321 | 0.0826 | 0.0420 | 0.790 | 0.126 |
| PPR | 0.0313 | 0.0771 | 0.0444 | 0.728 | 0.621 |

The blend is non-inferior to iALS by a wide margin (+0.0135 NDCG@10, 95% CI +0.0118 to +0.0153).
Whyfinder beats popularity on Recall@20 (+0.0119, CI +0.0078 to +0.0159) but not on NDCG@10
(−0.0007, CI −0.0026 to +0.0011, p = 0.78). Popularity is strong at the very top of a time-split
list, as studies of temporal evaluation have noted (Ji et al. 2023), and simple baselines are
often underrated (Ferrari Dacrema et al. 2019). It also recommends from 0.7% of the catalogue;
Whyfinder covers 30% at the same precision. The DPP raises ILD@10 from 0.777 to 0.828, closing 22.7%
of the headroom to 1, for an NDCG@10 cost of 0.0010.

The graph adds little accuracy over EASE^R alone (0.0456 against 0.0452 NDCG@10) but more coverage
(0.298 against 0.221), and it supplies the paths ("shares the tag Co-op with Portal 2") that
explanations quote.

**Explanations (test set).** Additivity 100%, counterfactual validity 100%, deletion 96.8%. On
validation the greedy counterfactual is on average 0.018 games larger than the exact minimum, and
the sanity correlation is 0.008.

## 5. Grounded words

Retrieval indexes 6,000 review quotes of at most 25 words from the training period. BM25 (Lucene
IDF) and dense vectors from latent semantic analysis (TF-IDF and a randomized SVD, Halko et al.
2011) are fused by reciprocal rank fusion (Cormack et al. 2009). The dense side runs on a
hand-written HNSW (Malkov and Yashunin 2020) whose recall@10 matches hnswlib's within a point at
every efSearch we tried (0.999 against 0.994 at efSearch 64 on the quote vectors), at about one
twentieth of its query rate. On 99,693 sentences from the full review corpus it still reaches 0.963
against hnswlib's 0.957, building in five minutes against eleven seconds.

For each pick we gather the facts: the top five attributions, the counterfactual set, two graph
paths, the variety flag, and quotes from the pick's reviews that mention an aspect it shares with
the top liked game. A checker accepts a sentence only if every game it cites is among the top five
with its exact share, every percentage is within a point of a cited share, every quote is a
verbatim span of a retrieved chunk, a counterfactual cites exactly the computed set, and no other
catalogue game is named. Template sentences built from the facts always pass.

We then asked three small local models (through Ollama, temperature 0, seed fixed) to write the
sentences from the same facts, citing numbered facts so that code attaches the evidence. Left free,
the best of them passed the checker within two tries on 32% of 60 picks. The failures were the same
across models: sentences praising the recommended game where the facts concern the liked game,
paraphrased quotes, and answers past the length limit.

Each of those failures is a property of the string, so we moved it into decoding. The model now
writes one sentence per fact, and the JSON schema sent with each prompt gives every fact its own
regular expression: the liked game's exact title, the listed percentage or none, a quote copied
between curly quotes, a bounded length. Ollama constrains generation to the schema; the checker
still runs afterwards.

| Model | Free: within two tries | Pinned: claims kept | Pinned: first try / two tries | Fallback | Cut off | Restates a fact |
| --- | --- | --- | --- | --- | --- | --- |
| qwen2.5:1.5b | 7% | 100% | 82% / 97% | 3% | 13% | 80% |
| qwen2.5:3b | 32% | 97% | 77% / 90% | 10% | 19% | 76% |
| llama3.2:3b | 13% | 99.4% | 98% / 100% | 0% | 8% | 53% |

With pinning, llama3.2:3b meets the 95% claim-support target and never falls back on this sample.
It also cites liked games in attribution order (Kendall τ = 1.0), and its first citation is the
true top contributor in every answer when given the shares, against 30% without them. The last two
columns are crude text proxies, and they show what the checker cannot: a sentence cut off at the
length bound, or one that repeats the fact line almost word for word (similarity at least 0.85),
is faithful and still no better than the template. The served system therefore keeps the template
sentences by default and uses a model only when one is configured.

**A second round.** We then tried to buy the wording back. Facts went into the prompt as data rows
under a heading per kind ("A1: Portal Stories: Mel, 62%"), leaving nothing to copy. The length
bounds came off, because every bound a model reached produced a word cut in half or a title spliced
into one; length was left to the checker's 60-word limit and its retry. Titles became matchable
without trademark signs, which also closed a gap in the checker: a game named without its ® had
passed unseen.

To read what the freed words say, a judge model (qwen2.5:7b, in the manner of Zheng et al. 2023)
labels each served sentence entailed, neutral or contradicted against all the facts. The template
sentences of the same picks are labelled as a control: they are faithful by construction, so the
judge's labels on them measure its own error. An NLI cross-encoder (DeBERTa-v3, He et al. 2023,
trained on MNLI, Williams et al. 2018) was tried first and labelled 91% of the template sentences
neutral, so it could not serve.

| Model | Claims kept | Passes first / two tries | Fallback | Cut off | Copies a line | Judge: entailed / neutral / contradicted |
| --- | --- | --- | --- | --- | --- | --- |
| qwen2.5:1.5b | 96.9% | 95% / 100% | 0% | 12% | 3% | 34% / 58% / 8% |
| qwen2.5:3b | 99.1% | 87% / 92% | 8% | 2% | 0% | 63% / 17% / 20% |
| llama3.2:3b | 98.3% | 78% / 88% | 12% | 4% | 0% | 38% / 44% / 18% |
| llama3.1:8b | 99.1% | 48% / 70% | 30% | 2% | 0% | 65% / 25% / 10% |
| qwen2.5:7b (judging itself) | 93.2% | 87% / 97% | 3% | 2% | 18% | 42% / 47% / 11% |
| Template sentences (control) | 100% | n/a | n/a | n/a | n/a | 64% / 32% / 4% |

Copying fell to 3% or less for every model but qwen2.5:7b (18%), and cut-offs to 4% or less from
3B up. The cost moved elsewhere. The judge finds 8% to 20% of model sentences contradicted, against
4% for the template, and the ones we read were real misreadings: the counterfactual taken for a
dislike ("You didn't like I am Bread, which was a reason why Surgeon Simulator was recommended"),
or a share of the reasons retold as a share of players. With room to write, the 8B model also ran
past the word limit and fell back on 30% of picks. When it did speak, its sentences were entailed
as often as the template's, which makes it the default model; the template stays the default
explanation.

## 6. Limitations

The data end in 2017 and cover English reviews. Play time is a noisy proxy for preference. The
item cap keeps the long tail out of EASE^R, though PPR still reaches it. The retrieval layer has
not yet been measured against labelled queries (the sheet and guide are ready). The generation
study uses 60 picks, models small enough for a CPU runner, and text proxies in place of human
judgements of fluency. Its judge calls a third of the faithful template sentences something other
than entailed, so only large gaps in its labels mean much; the contradictions are the clearest of
them.

## 7. Conclusion

Restricting a recommender to additive parts lets every explanation be exact and every claim be
checked, at an accuracy that matches strong baselines on this data. Pinning generated sentences
to those facts makes even a 3B model faithful to what a checker can parse; loosening the pins to
get better wording lets the same models misread the facts one sentence in five. The checker alone
cannot see that, and a judge with a control can. The one target we missed, and the gap between faithful and
fluent, are as much a result as the targets we met: both came from measuring against commitments
made in advance.

## References

- Adebayo, J. et al. Sanity checks for saliency maps. NeurIPS 2018.
- Andersen, R., Chung, F., Lang, K. Local graph partitioning using PageRank vectors. FOCS 2006.
- Chen, L., Zhang, G., Zhou, H. Fast greedy MAP inference for determinantal point process to improve recommendation diversity. NeurIPS 2018.
- Cormack, G., Clarke, C., Büttcher, S. Reciprocal rank fusion outperforms Condorcet and individual rank learning methods. SIGIR 2009.
- Ferrari Dacrema, M., Cremonesi, P., Jannach, D. Are we really making much progress? A worrying analysis of recent neural recommendation approaches. RecSys 2019.
- Ghazimatin, A., Balalau, O., Saha Roy, R., Weikum, G. PRINCE: Provider-side interpretability with counterfactual explanations in recommender systems. WSDM 2020.
- Halko, N., Martinsson, P.-G., Tropp, J. Finding structure with randomness. SIAM Review 2011.
- He, P., Gao, J., Chen, W. DeBERTaV3: Improving DeBERTa using ELECTRA-style pre-training with gradient-disentangled embedding sharing. ICLR 2023.
- Holm, S. A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics 1979.
- Hu, Y., Koren, Y., Volinsky, C. Collaborative filtering for implicit feedback datasets. ICDM 2008.
- Ji, Y., Sun, A., Zhang, J., Li, C. A critical study on data leakage in recommender system offline evaluation. ACM TOIS 2023.
- Kang, W.-C., McAuley, J. Self-attentive sequential recommendation. ICDM 2018.
- Malkov, Y., Yashunin, D. Efficient and robust approximate nearest neighbor search using hierarchical navigable small world graphs. IEEE TPAMI 2020.
- Pathak, A., Gupta, K., McAuley, J. Generating and personalizing bundle recommendations on Steam. SIGIR 2017.
- Petsiuk, V., Das, A., Saenko, K. RISE: Randomized input sampling for explanation of black-box models. BMVC 2018.
- Rendle, S., Krichene, W., Zhang, L., Koren, Y. Revisiting the performance of iALS on item recommendation benchmarks. RecSys 2022.
- Steck, H. Embarrassingly shallow autoencoders for sparse data. WWW 2019.
- Wan, M., McAuley, J. Item recommendation on monotonic behavior chains. RecSys 2018.
- Williams, A., Nangia, N., Bowman, S. A broad-coverage challenge corpus for sentence understanding through inference. NAACL 2018.
- Zheng, L. et al. Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. NeurIPS 2023.
