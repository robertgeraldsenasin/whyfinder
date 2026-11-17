# ADR-0011: DPP re-ranking for variety

- **Status:** Accepted
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

Item-item models over-recommend near-duplicates (ten roguelikes for a roguelike fan).

## Options considered

1. No re-ranking
2. Genre caps
3. MMR
4. DPP greedy MAP

## Decision

Greedy MAP inference on a DPP with kernel Diag(q)·S·Diag(q) (Chen, Zhang, Zhou, NeurIPS 2018) over the top 100 candidates; θ tuned so NDCG@10 drops ≤ 0.005. Picks that DPP added over higher-scored ones are flagged "kept for variety".

## Consequences

Principled variety with a measurable cost; the flag keeps explanations honest.
