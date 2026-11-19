# ADR-0012: Counterfactual search modes and guarantees

- **Status:** Accepted
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

Exact minimal sets can need many pipeline runs; the API must stay fast.

## Options considered

1. Exact everywhere
2. Greedy everywhere
3. Greedy live, exact offline

## Decision

Live: greedy removal by contribution, then pruning → a valid, irreducible set (O(|H|) runs). Offline: exact minimum over subsets of size ≤ 3 of the 20 largest contributors. The UI states which guarantee applies; the minimality gap is tracked.

## Consequences

Fast API, honest guarantees, a measurable gap.

The iALS rival uses the same live search; its re-scoring uses Sherman–Morrison downdates instead of re-solving (2026-11-20, issue #25), so the guarantee carries over unchanged.
