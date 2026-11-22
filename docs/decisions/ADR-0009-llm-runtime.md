# ADR-0009: LLM: local model through Ollama, cached in CI

- **Status:** Accepted (model chosen 2026-11-23)
- **Date:** 2026-11-17, amended 2026-11-20 and 2026-11-23
- **Deciders:** Robert Gerald Senasin

## Context

Paid API calls in CI cost money and make results non-deterministic. This record left the model to
be chosen in M3, with its name and digest recorded.

## Options considered

1. Hosted API
2. Local model through Ollama
3. Both

## Decision

Default to a small open instruct model through Ollama. Generations are cached under hash(model,
digest, prompt, output schema, seed); CI replays the cache and fails on a miss. A hosted model may
be compared locally, never in CI.

**How the model is asked.** Each fact it may use is numbered (A for an attribution with its
percentage, C for the counterfactual set, Q for a review quote). The model writes one to three
sentences, each about one fact, and gives that fact's ID; code attaches the evidence. The per-prompt
JSON schema pins every sentence to its fact with a pattern: the liked game's exact title, no
percentage other than the listed one, a quote verbatim between curly quotes, a bounded length.
Ollama enforces the schema while decoding, and the checker still verifies the result.

**What was measured** (60 picks, `results/validation/rag-eval-*.json`, the llm workflow on GitHub's
standard runner, temperature 0, seed 20261117). Free sentences citing fact IDs came first; pinned
sentences replaced them:

| Model (digest prefix) | Free: passes within two tries | Pinned: claims kept, first try | Pinned: passes first try / within two | Pinned: fallback | Cut off | Copies a fact line |
| --- | --- | --- | --- | --- | --- | --- |
| qwen2.5:1.5b (65ec0654) | 7% | 100% | 82% / 97% | 3% | 13% | 80% |
| qwen2.5:3b (357c53fb) | 32% | 97% | 77% / 90% | 10% | 19% | 76% |
| **llama3.2:3b** (a80c4f17) | 13% | **99.4%** | **98% / 100%** | **0%** | 8% | 53% |

`llama3.2:3b` is the default (`whyfinder rag eval --model`): it meets the 95% claim-support target
of 06_RAG, never needs the fallback on this sample, and cites liked games in attribution order
(τ = 1.0, the true top contributor first in 100% of answers against 30% when it is not given the
shares). Free generation failed in the ways pinning removes: praising the recommended game instead
of naming the liked one, paraphrasing quotes, running long.

The checker guards faithfulness, not prose. Half of llama3.2:3b's sentences only restate a fact
line, and 8% are cut off by the length bound mid-phrase, so a generated explanation reads no better
than the template more often than not. Generation therefore stays opt-in: the API uses a model only
when one is configured, and the static demo keeps the template sentences.

## Consequences

CI costs $0 and is deterministic. Pinning makes even 1.5B models faithful to the facts; what they
add over the template is wording, and on this sample not much of it. Next to try: a 7B model on a
longer runner, and a looser length bound that ends sentences instead of cutting them.
