# ADR-0007: Glass-box blend: EASE^R + Personalized PageRank, iALS as rival

- **Status:** Accepted
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

The project's claim is exact, verifiable explanations. Latent-factor models give attributions that depend on the whole history, so counterfactuals need search. Common student stacks (MF, BPR, two-tower) add little new.

## Options considered

1. iALS (+ BPR, two-tower)
2. EASE^R alone
3. PPR alone
4. Additive blend of EASE^R and PPR

## Decision

Score with M = β·B/c_B + (1−β)·Π/c_Π (EASE^R + PPR over a game–tag–developer–co-play graph), stored as top-500-per-row CSR. Both parts are linear in the user's history, so attributions and counterfactual re-scoring are exact. Keep iALS as the rival the blend must match; drop BPR and the two-tower model.

## Consequences

Explanations are exact for the served model; scoring is a sparse product (fast). PPR adds metadata and cold-ish items. Truncation of M is reported as an NDCG delta. The research question becomes "glass box vs black box".
