# ADR-0002: Interactions from dated reviews, global time split

- **Status:** Accepted (confirmed in M0 by the first full data run, 2026-11-17)
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

Random splits leak the future into training and inflate recommender metrics. Version 2 Steam reviews appear to carry dates and hours played; Version 1 playtime data has no dates.

## Options considered

1. Global time split on Version 2 reviews
2. Leave-last-out per user
3. Random per-user holdout on Version 1

## Decision

Use Version 2 reviews as interactions (review = positive, hours = confidence) with global cut-offs T1 < T2 at the 80% and 90% date quantiles. Users with 1–4 training interactions form a cold-start set. If more than 10% of rows lacked a date, the split would fall back to leave-last-out by review order (implemented and tested, not needed).

## Evidence (data/stats.json, data/split.json)

| Check | Result |
| --- | --- |
| Reviews parsed | 7,793,069, 0 malformed |
| Rows with a date | 100.0% (2010-10-15 to 2018-01-05) |
| Rows with hours played | 99.63% |
| After dedupe | 6,889,728 (user, game) pairs, 2,567,538 users, 15,474 games |
| After the 5-core | 3,484,694 pairs, 281,210 users, 11,961 games (6 passes) |
| Cut-offs | T1 = 2017-05-31, T2 = 2017-10-01 |
| Train / validation / test | 2,787,177 / 183,974 (70,170 users) / 158,074 (66,095 users) |
| Cold-start set | 148,614 rows, 52,831 users |

Date coverage is far above the 90% threshold, so the global time split stands.

## Consequences

Honest, harder numbers: the test set is the future. Two costs are now measured rather than assumed:
validation and test lose 59,737 and 87,735 rows on games released or first reviewed after T1
(item-based models cannot score a game they have never seen; the cold-item problem is out of scope for v1),
and 24,801 / 34,582 rows from users with no history before T1. Version 1 becomes a robustness check only.
