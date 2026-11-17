# ADR-0003: DVC pipeline; CI uses a pinned subsample

- **Status:** Proposed
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

Raw data is 1.3 GB and must not live in Git; CI must be fast and reproducible.

## Options considered

1. DVC with a remote (Google Drive or DagsHub)
2. Plain scripts with checksums
3. LakeFS

## Decision

DVC stages for the whole pipeline with `params.yaml`. Full artifacts in a DVC remote (choose Google Drive or DagsHub when setting up M0 and record it here). CI downloads only a processed 5% user subsample published as a GitHub release asset `data-ci-v1`, verified by SHA-256.

## Consequences

Anyone can reproduce numbers with `make reproduce`; CI never touches raw data.
