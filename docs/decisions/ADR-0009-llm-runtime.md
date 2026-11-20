# ADR-0009: LLM: local model through Ollama, cached in CI

- **Status:** Accepted (model measured 2026-11-20)
- **Date:** 2026-11-17, amended 2026-11-20
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

The model numbers each fact it may use, writes one to three sentences and gives the IDs each one
relies on; the IDs are an enum in the per-prompt output schema and code attaches the evidence. A
first version that asked the model to copy game IDs, shares and quotes into the claim schema kept
30% of its claims (qwen2.5:1.5b), drifted into Chinese on the blind prompt and looped on arrays.

Three CPU-sized models were run on the same 60 picks (`results/validation/rag-eval-*.json`, the
llm workflow on GitHub's standard runner, temperature 0, seed 20261117):

| Model (Ollama tag, digest prefix) | Claims kept, first try | Output passes within two tries | Fallback | τ (citation vs attribution order) | Top-1 cited, with / without shares |
| --- | --- | --- | --- | --- | --- |
| qwen2.5:1.5b (65ec0654) | 18% | 7% | 93% | 0.96 | 98% / 37% |
| **qwen2.5:3b** (357c53fb) | 27% | **32%** | **68%** | 0.94 | 88% / 57% |
| llama3.2:3b (a80c4f17) | 35% | 13% | 87% | 0.95 | 98% / 33% |

`qwen2.5:3b` is the default (`whyfinder rag eval --model`), as the one whose answers most often
survive the checker. None reaches the 95% claim-support target of 06_RAG. The models follow the
attribution order closely (τ ≈ 0.95), and giving them the shares moves the first liked game they
cite from about a third right to nearly always right, but they write praise of the recommended game
where the facts call for the liked game's name, paraphrase quotes, and run past 60 words.

So generation stays opt-in. The API serves the template sentences unless a model is configured, and
when one is, every answer still passes the checker or is replaced.

## Consequences

CI costs $0 and is deterministic. Quality depends on the local model; the claim checker and the
template fallback keep what users see faithful regardless. A bigger model (7B and up) or a
narrower output (one fact per sentence, the quote inserted by code) are the next things to try; the
evaluation and cache make the comparison one workflow run.
