# ADR-0004: Item cap for EASE^R and confidence weighting

- **Status:** Proposed
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

EASE^R needs an n × n inverse: 15,474 games would need ~1.9 GB per float64 matrix. Hours played are heavy-tailed.

## Options considered

1. All games
2. Cap at N_max most-interacted games (default 8,000)
3. Block-sparse approximations

## Decision

Cap the catalogue at N_max (default 8,000, a parameter) by train interaction count; long-tail games stay reachable through PPR and appear in the catalogue. Confidence x = 1 + α·log(1 + hours/ε), α and ε tuned on validation; binary as an ablation.

## Consequences

Peak memory under 8 GB. Coverage metrics show the cap's effect; the cap is reported in every run.
