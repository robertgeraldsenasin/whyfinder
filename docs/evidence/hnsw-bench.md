# HNSW: the hand-written graph against hnswlib

FR-15 asks for the hand-written HNSW (`src/whyfinder/rag/hnsw.py`) to reach recall@10 ≥ 0.95 against
exact search and to be benchmarked against hnswlib, the reference C++ implementation by the
algorithm's authors. `scripts/bench_hnsw.py` runs both with M = 16, efConstruction = 200, inner
product and one thread; `.github/workflows/bench.yml` runs it on GitHub's standard runner. These
numbers are from the run on PR #82 (hnswlib 0.8.0, Python 3.12).

### Review quotes as LSA vectors (5,800 vectors, 128 dimensions, 200 held-out queries)

Build: ours 19.4 s, hnswlib 0.58 s.

| efSearch | recall@10, ours | recall@10, hnswlib | QPS, ours | QPS, hnswlib |
| --- | --- | --- | --- | --- |
| 16 | 0.945 | 0.938 | 2,911 | 77,678 |
| 32 | 0.985 | 0.977 | 1,778 | 38,995 |
| 64 | 0.999 | 0.994 | 1,143 | 22,196 |
| 128 | 1.000 | 1.000 | 669 | 13,325 |

### Random unit vectors (10,000 vectors, 32 dimensions, 200 queries)

Build: ours 30.5 s, hnswlib 0.89 s.

| efSearch | recall@10, ours | recall@10, hnswlib | QPS, ours | QPS, hnswlib |
| --- | --- | --- | --- | --- |
| 16 | 0.691 | 0.697 | 2,466 | 85,185 |
| 32 | 0.862 | 0.853 | 1,979 | 44,919 |
| 64 | 0.960 | 0.960 | 1,135 | 27,305 |
| 128 | 0.993 | 0.994 | 632 | 15,551 |

**Reading it.** The graphs are equally good: at every efSearch the two recalls are within a point
of each other, and at the served setting (efSearch = 64) ours reaches 0.999 on the quotes and 0.960
on the harder random set, both above the 0.95 bar. The cost is speed: pure Python builds about 30
times slower and answers about 20 times fewer queries per second than C++. For the API that is
still about 1 ms a query, and the 20 s build happens once at start-up.
