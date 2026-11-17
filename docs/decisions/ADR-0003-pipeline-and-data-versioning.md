# ADR-0003: DVC pipeline without a remote; data runs on GitHub Actions; CI uses a pinned subsample

- **Status:** Accepted (M0, 2026-11-17)
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

Raw data is 1.3 GB and must not live in Git; CI must be fast and reproducible. The original plan
left the DVC remote (Google Drive or DagsHub) to be chosen in M0. M0 showed two things: the raw files
download in about 80 seconds on a GitHub runner and the whole pipeline runs in about 3 minutes
there, and the sandboxed development environment cannot reach the UCSD servers at all.

## Options considered

1. DVC with a remote (Google Drive or DagsHub)
2. DVC without a remote: rebuild from the checksummed raw files; publish small derived assets as releases
3. Plain scripts with checksums
4. LakeFS

## Decision

Option 2.

- `dvc.yaml` + `params.yaml` + `dvc.lock` describe and record the pipeline
  (fetch → parse → clean → kcore → split → features → subsample → stats → export_demo). Raw files are a
  persistent, uncached output verified in place against `data/checksums.txt`.
- `.github/workflows/data.yml` (manual) runs the full pipeline on GitHub's runners and publishes the
  release `data-ci-v1`: the 5% hash-chosen user subsample, `split.json`, `stats.json`, `checksums.txt`,
  `dvc.lock` and the demo slice, with `SHA256SUMS`. The same commands run on a laptop.
- `data/checksums.txt`, `data/split.json`, `data/stats.json` and `dvc.lock` are committed, so every
  number has a reviewable source. Raw and processed tables never enter Git.
- CI never downloads raw data.

## Consequences

No credentials and no storage bill. Rebuilding the processed tables costs ~5 minutes of runner time
instead of a `dvc pull`. Revisit when M1's model artifacts (EASE^R at 8,000 games, Π, iALS factors)
make rebuilds slow: then add a remote and record the choice here.
