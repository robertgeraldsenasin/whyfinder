# ADR-0002: Interactions from dated reviews, global time split

- **Status:** Proposed (confirm in M0)
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

Random splits leak the future into training and inflate recommender metrics. Version 2 Steam reviews appear to carry dates and hours played; Version 1 playtime data has no dates.

## Options considered

1. Global time split on Version 2 reviews
2. Leave-last-out per user
3. Random per-user holdout on Version 1

## Decision

Use Version 2 reviews as interactions (review = positive, hours = confidence) with global cut-offs T1 < T2. Users with 1–4 training interactions form a cold-start set. If more than 10% of rows lack a date, switch to leave-last-out by review order and record it here.

## Consequences

Honest, harder numbers. The test set reflects future behaviour. Version 1 becomes a robustness check only.
