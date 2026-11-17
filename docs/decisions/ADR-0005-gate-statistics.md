# ADR-0005: Quality gates: paired bootstrap non-inferiority, sealed test set

- **Status:** Accepted
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

Hasik's SPRT suits games played one at a time. Offline recommender evaluation has every test user available at once, and repeated PRs can overfit a test set.

## Options considered

1. Paired bootstrap
2. Paired t-test
3. SPRT
4. Fixed thresholds

## Decision

Paired bootstrap over users (2,000 resamples, 95% interval, fixed seed), Holm–Bonferroni across gated metrics. Default non-inferiority (lower bound > −δ); superiority with label `model:gainer`. PR gates use the validation subsample; the test set is scored only at release.

## Consequences

Robust to non-normal per-user metrics; no test-set leakage through PRs. Margins δ live in ADR-0006.
