# Whyfinder: a recommender that can show its work

*Robert Gerald Senasin · November 2026 · [repository](https://github.com/robertgeraldsenasin/whyfinder) ·
[live demo](https://robertgeraldsenasin.github.io/whyfinder/)*

## The question

Most recommenders can tell you *what* to play next. Very few can tell you *why* in a way you could
check. "Because you played Dead Cells" is usually a story written after the fact by a second system,
not the reason the first one ranked the game. I wanted to build one where the reason and the ranking
are the same arithmetic, and then prove it on real data, with the test set locked away until the end.

## What I built

The model is a blend of two methods that are both additive over a player's history: EASE^R, a
closed-form item-to-item model, and Personalized PageRank over a graph of games, tags, developers,
publishers and co-play. Because each liked game contributes a separate term to every score, "42% of
this pick came from Dead Cells" is not an estimate. It is the term, and CI checks that the terms sum
to the score within 1e-9 on every change.

On top of that:

- **Counterfactuals.** The smallest set of your games whose removal drops a pick, found by re-running
  the whole pipeline, greedy then pruned, with an exact search offline to measure how far greedy is
  from the true minimum (0.018 games on average).
- **Variety.** A determinantal point process re-ranks the top ten so it isn't ten copies of one game,
  and a pick kept for variety says so.
- **A rival.** iALS, a latent-factor model, implemented by hand, including Sherman–Morrison updates so
  its counterfactuals are cheap too.
- **Words.** Review retrieval written from scratch (BM25, LSA vectors, an HNSW graph, rank fusion)
  supplies quotes from players of the recommended game. A claim checker rejects any sentence whose
  numbers, quotes or game names don't match the computed facts.
- **Delivery.** A REST API with an OpenAPI contract tested by Schemathesis, a Docker image, and a
  browser demo that runs the same engine in TypeScript, golden-matched to the Python output.

The core algorithms are hand-written; libraries like hnswlib appear only as test oracles or
benchmarks.

## How I kept myself honest

The success targets were written down before any test-set number existed (ADR-0006), adjusted once
after validation baselines, and then frozen. Every pull request runs a quality gate: a paired
bootstrap non-inferiority test against `main` on ranking and explanation metrics, with Holm
correction. To check that the gate actually blocks things, I opened a PR that deliberately broke
the model. The gate failed it, and it also failed the deletion test on an unchanged mean, which told
me that check's sample was too small for its margin. I fixed the sample size rather than the
margin.

The test split is read in exactly one place, the release workflow, and only once per release.

## What the numbers say

On 20,000 held-out users (time split, Steam data from 2017):

| | Whyfinder | Popularity | iALS |
| --- | --- | --- | --- |
| NDCG@10 | 0.0447 | 0.0454 | 0.0321 |
| Recall@20 | 0.1194 | 0.1075 | 0.0826 |
| Catalogue covered in top 10 | 30% | 0.7% | 13% |

The blend beats the latent-factor rival clearly, and beats popularity on recall. It does not beat
popularity on NDCG@10: the difference is inside the noise (p = 0.78). That was one of my targets
and it was missed. Popularity is a strong baseline at the very top of a time-split list, because the
games everyone starts playing next really are what many users play next. Whyfinder gets the same
precision while recommending from 40 times more of the catalogue, and every one of its reasons is
exact. The explanation checks all pass: additivity and counterfactual validity are 100%, and
removing the three most-attributed games pushes a pick further down than removing three random ones
for 96.8% of users.

## What I learned

- Exactness is a design constraint, not a feature you add later. Choosing additive models up front
  is what made every other explanation cheap to compute and possible to test.
- Write the targets before looking. The NDCG miss is more useful to me, and I think more credible
  to a reader, than a target quietly moved to fit.
- A gate you have never seen fail is a gate you don't know works.
- Pure Python HNSW matches hnswlib's recall at every setting I tried and is about 20 times slower.
  For 6,000 vectors that's fine; I know where the line is.

## What's next

I also let small local models write the sentences, with the checker as a gate. Left free, the best
of three passed within two tries only 32% of the time: they praised the recommended game instead
of naming the liked one and paraphrased quotes. So I pinned each sentence to one fact while the
model decodes, with a pattern that forces the exact title, the listed percentage and verbatim
quotes. llama3.2:3b then kept 99.4% of its claims and never needed the fallback. The catch: half
its sentences just restated the fact.

The second round tried to buy fluency back. Facts went into the prompt as data rows, so there was
nothing to copy, and the length bounds came off, because every bound a model hit came out as a
word sliced in half. Copying all but disappeared for four of the five models. To see what the freed-up words actually said, I added a
judge model, with the template sentences as its control: it calls 4% of those contradicted, and
they are right by construction, so that is the judge's own error. Against that, the models
contradicted the facts in 8% to 20% of their sentences: "You didn't like I am Bread", for a game
the player did like. The best, llama3.1:8b, matched the template on entailment when it spoke. The checker
also had a gap I only found because of trademark signs: a game named without its ® slipped past.
That's fixed. The templates stay the default. Next: 150 hand-labelled retrieval queries, so
retrieval quality is measured rather than assumed; the sheet and the guide are ready.
