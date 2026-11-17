# Workflow

## Every change

1. Pick an issue from the current milestone (GitHub Project board: Backlog → Ready → In progress → In review → Done).
2. `git switch -c feat/<issue>-<slug>`
3. Write the test first when you can (oracle or property test for algorithms).
4. `make verify`
5. Commit with Conventional Commits, citing requirement IDs: `feat(graph): PPR forward push (FR-07)`.
6. Push, open a PR from the template; CI (and the quality gate from M1) must be green.
7. Squash merge; the branch is deleted automatically.

## Authorship

All commits are authored and committed as Robert Gerald Senasin. No co-author trailers, "generated with"
lines, session links or AI-tool mentions anywhere in the repository history, PRs or issues.

## Milestone end

Gates green on `main` → update CHANGELOG → `git tag vX.Y.Z && git push --tags` → `release.yml` scores the
sealed test set and publishes → README tables regenerate → a GIF or screenshot of what's new.

## When a decision changes

Write a new ADR from `docs/decisions/ADR-template.md` (next number), mark the old one "Superseded by", and
link both from `docs/decisions/README.md` in the same PR.
