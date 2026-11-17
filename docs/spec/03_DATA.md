# 03 · Data

Source: the UCSD McAuley Lab Steam datasets (<https://cseweb.ucsd.edu/~jmcauley/datasets.html>). The
page lists 7,793,069 reviews, 2,567,538 users and 15,474 games across its Steam files.

| File | Size | Used for |
| --- | --- | --- |
| `steam_reviews.json.gz` (Version 2) | 1.3 GB | Main interactions (review = positive signal; hours played = confidence) and the RAG corpus |
| `steam_games.json.gz` (Version 2) | 2.7 MB | Game metadata: title, tags, genres, developer, publisher, price, release date → catalogue and graph |
| `australian_users_items.json.gz` (Version 1) | 71 MB | Robustness dataset: owned games with playtime |
| `australian_user_reviews.json.gz` (Version 1) | 6.7 MB | Recommend / not-recommend labels for an explanation sanity check |
| `bundle_data.json.gz` | 92 KB | Optional: bundle co-membership edges in the graph |

**Terms.** The page gives no licence; it asks users to cite the papers: Kang & McAuley (ICDM 2018),
Wan & McAuley (RecSys 2018), Pathak, Gupta & McAuley (SIGIR 2017). Whyfinder downloads by script,
cites them in `CITATION.cff` and the README, and never commits or redistributes raw files.

**Format note.** These files are Python-literal dicts per line (single quotes), not strict JSON. Parse
with `ast.literal_eval` in a streaming reader, never by loading the whole file.

## Pipeline (DVC stages)

`fetch → parse → clean → kcore → split → features → graph → index`

| Stage | Output | Key rules |
| --- | --- | --- |
| fetch | `data/raw/*.gz` | SHA-256 recorded in `data/checksums.txt`; retries with backoff |
| parse | `data/interim/*.parquet` | Streaming parse; malformed lines counted, not fatal (limit 0.1%) |
| clean | `interactions.parquet`, `games.parquet` | Drop rows without user or game; dedupe (user, game) keeping max hours; salted SHA-256 of usernames; clip hours at the 99.9th percentile |
| kcore | `interactions_k.parquet` | Iterate until users and games all have ≥ k interactions (k = 5) |
| split | `train/valid/test.parquet`, `split.json` | Global time cut-offs T1 < T2; test users must have train history; users with 1–4 train items → `cold.parquet` |
| features | `X_train.npz`, `items.parquet` | Confidence x = 1 + α·log(1 + hours/ε); item cap N_max (ADR-0004) |
| graph | `graph.npz`, `nodes.parquet` | See 04_ALGORITHMS.md §A4 |
| index | `chunks.parquet`, `bm25.npz`, `hnsw.bin` | See 06_RAG.md |

**CI subsample:** a fixed, hashed 5% of users (and their games), published as a GitHub release asset
`data-ci-v1` with its checksum, so CI never downloads the raw data.

## Data contracts (Pandera, checked in `features` and in CI)

- Column types and non-null keys.
- Unique (user, game); hours ≥ 0; every game ID present in `games.parquet`.
- Split cut-offs monotonic; no user in test without train history.
- Row counts within 1% of the counts recorded in `data/stats.json`.

## Assumption to confirm in M0

That Version 2 reviews carry a date and hours played for nearly all rows. If more than 10% lack a
date, fall back to leave-last-out by review order (ADR-0002). Record the real numbers in
`data/stats.json`.
