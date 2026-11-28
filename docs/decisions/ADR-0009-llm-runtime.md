# ADR-0009: LLM: local model through Ollama, cached in CI

- **Status:** Accepted (model chosen 2026-11-23, chosen again after the second round 2026-11-28)
- **Date:** 2026-11-17, amended 2026-11-20, 2026-11-23 and 2026-11-28
- **Deciders:** Robert Gerald Senasin

## Context

Paid API calls in CI cost money and make results non-deterministic. This record left the model to
be chosen in M3, with its name and digest recorded.

## Options considered

1. Hosted API
2. Local model through Ollama
3. Both

## Decision

Default to an open instruct model through Ollama. Generations are cached under hash(model, digest,
prompt, output schema, seed); CI replays the cache and fails on a miss. A hosted model may be
compared locally, never in CI. Model-written sentences are opt-in: without a configured model the
API and the demo serve the template sentences.

**How the model is asked.** Each fact it may use is numbered under a heading that says what that
kind of fact means: A for a liked game and its share of the reasons, C for the counterfactual set, Q
for a review quote. The rows are data ("A1: Portal Stories: Mel, 62%"), not sentences a model can
copy. The model writes one or two sentences, each using one fact and giving its ID; code attaches
the evidence. The per-prompt JSON schema pins every sentence to its fact with a pattern: the liked
game's title (trademark signs optional), no percentage other than the listed one, a quote verbatim
between curly quotes, a full stop at the end. Ollama enforces the schema while decoding, and the
checker still verifies the result, with one retry before the template takes over.

### Round 1 (2026-11-23)

Facts were listed as sentences ("A1: Portal 2 counted for 62% of the score") and every pattern had
a tight length bound. Numbers from the llm workflow on #87 (60 picks, temperature 0, seed
20261117); free sentences citing fact IDs came first, pinned sentences replaced them:

| Model (digest prefix) | Free: passes within two tries | Pinned: claims kept, first try | Pinned: passes first try / within two | Pinned: fallback | Cut off | Copies a fact line |
| --- | --- | --- | --- | --- | --- | --- |
| qwen2.5:1.5b (65ec0654) | 7% | 100% | 82% / 97% | 3% | 13% | 80% |
| qwen2.5:3b (357c53fb) | 32% | 97% | 77% / 90% | 10% | 19% | 76% |
| llama3.2:3b (a80c4f17) | 13% | 99.4% | 98% / 100% | 0% | 8% | 53% |

Pinning made every model faithful to what the checker reads, and llama3.2:3b became the default.
But half its sentences copied a fact line back and 8% were cut off by a bound, and nothing measured
the words around the pinned parts.

### Round 2 (2026-11-28)

**What changed, and why.** Each change answers something the round-1 outputs or the intermediate
runs of this round showed (llm runs 46073509623, 46080650824 and 46086701897):

- Facts became data rows under headings, which ended the verbatim copying. Terse labels on each
  row were tried first and misread ("84% of players", "removed from the list"); a heading per kind
  of fact fixed that.
- Every bound a model wanted to pass came out as a spliced or truncated word: a 50-character lead
  forced titles in mid-word, a 55-character tail cut "AdVenture Capitalis.". The bounds are now
  generous and length is left to the checker's 60-word limit, with its retry. Sentences must end
  with a full stop, and free text excludes brackets and line breaks, which models used to leave
  as JSON debris.
- Models write "BioShock 2" for "BioShock® 2". Forcing the sign spliced it into words, and the
  checker could not see an outside game named without its sign either. Trademark signs are now
  optional in patterns and ignored when both checkers compare titles.
- Answers are one or two sentences of at most 25 words, so two of them fit the limit.
- When Ollama stops a model that loops on one token, that answer fails like any other (retry,
  then template) instead of ending the run.

**Entailment.** The checker proves titles, shares, quotes and the counterfactual set; whatever a
model writes around them went unread. A judge model, qwen2.5:7b, now labels each served sentence
entailed, neutral or contradicted against every fact the model was given, stated in plain words.
The template sentences of the same picks are labelled too. They are faithful by construction, so
the judge's labels on them are its error rate: it calls 64% of them entailed and 4% contradicted.
Model numbers mean something only next to that. An NLI cross-encoder (DeBERTa-v3 trained on MNLI),
which 06_RAG first named, was tried on the same sentences and labelled 91% of the template neutral,
so it cannot read facts of this kind and was dropped.

**What was measured** (60 picks, `results/validation/rag-eval-*.json`, llm runs 46098115558 and
46106133059):

| Model (digest prefix) | Claims kept, first try | Passes first try / within two | Fallback | Cut off | Copies a fact line | Adds at most one word | Judge: entailed / neutral / contradicted |
| --- | --- | --- | --- | --- | --- | --- | --- |
| qwen2.5:1.5b (65ec0654) | 96.9% | 95% / 100% | 0% | 12% | 3% | 19% | 34% / 58% / 8% |
| qwen2.5:3b (357c53fb) | 99.1% | 87% / 92% | 8% | 2% | 0% | 18% | 63% / 17% / 20% |
| llama3.2:3b (a80c4f17) | 98.3% | 78% / 88% | 12% | 4% | 0% | 53% | 38% / 44% / 18% |
| **llama3.1:8b** (46e0c10c) | 99.1% | 48% / 70% | 30% | 2% | 0% | 33% | **65% / 25% / 10%** |
| qwen2.5:7b (845dbda0), judging itself | 93.2% | 87% / 97% | 3% | 2% | 18% | 66% | 42% / 47% / 11% |
| *Template sentences (control)* | 100%, by construction | n/a | n/a | n/a | n/a | n/a | 64% / 32% / 4% |

**Reading it.** Copying is nearly gone: 3% or less for every model but qwen2.5:7b (18%), against
half or more in round 1. Cut-offs fall to 4% or less from 3B up; the 1.5B model is still cut off in
12% of its sentences. The cost moved to two places. First, the judge finds contradictions in 8% to
20% of model sentences against 4% for the template, and the ones read by hand are real misreadings:
the counterfactual heading taken for a dislike ("You didn't like I am Bread, which was a reason why
Surgeon Simulator was recommended"), a share of the reasons retold as a share of players. Second,
with room to write, longer answers pass the 60-word limit and fall back, most of all for the 8B
model. A fallback is safe, since the reader gets the checked template.

**The default model is llama3.1:8b.** When it speaks, its sentences are entailed as often as the
template's (65% against 64%) and contradict in 10% of cases, and it is not judged by its own family.
qwen2.5:1.5b contradicts a little less (8%), but the judge finds most of what it says unsupported
by the facts (58% neutral), and an eighth of its sentences are cut off. qwen2.5:7b falls back less,
but its numbers come from judging itself. Round 1 was never judged, so this record does not claim
round 2 is more or less faithful than round 1, only that its sentences copy far less.

## Consequences

CI costs $0 and is deterministic: generations and judgments are both replayed. Model-written
sentences stay opt-in, because at their best they match the template on entailment and at worst
contradict the facts one time in five, while the template is right by construction. The useful
work left is fluency within the word limit (an 8B model that keeps to it), and a stronger judge
from outside the models being compared.
