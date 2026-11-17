# Contributing

Thanks for looking. Whyfinder is a personal project with a strict workflow so every change can be traced.

1. **Open or pick an issue.** Each one cites requirement IDs from `docs/spec/02_REQUIREMENTS.md`.
2. **Branch:** `feat/<issue>-<slug>`, `fix/<issue>-<slug>` or `docs/<slug>`.
3. **Commit** with [Conventional Commits](https://www.conventionalcommits.org/): `feat(core): EASE^R closed form (FR-05)`.
4. **Check locally:** `make verify`.
5. **Open a PR** using the template: what and why, requirement IDs, how it was tested, gate result.
6. **Merge:** squash only, once `ci` (and `quality-gate` when it applies) are green.

Rules that reviews check (also in `CLAUDE.md`): hand-written core with oracle tests; no unseeded randomness
or wall-clock time in model code; pure functions; import boundaries; exact attributions; the test set is
sealed until release; a changed decision needs an ADR.

Questions or ideas: open a discussion or an issue with the `type:docs` label.
