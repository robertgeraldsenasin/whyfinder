# ADR-0009: LLM: local model through Ollama, cached in CI

- **Status:** Accepted
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

Paid API calls in CI cost money and make results non-deterministic.

## Options considered

1. Hosted API
2. Local model through Ollama
3. Both

## Decision

Default to a small open instruct model through Ollama (choose the model in M3; record name and digest). Generations are cached under hash(prompt, model digest); CI replays the cache and fails on a miss. A hosted model may be compared locally, never in CI.

## Consequences

CI costs $0 and is deterministic. Quality depends on the local model; the claim checker and template fallback guarantee faithfulness regardless.
