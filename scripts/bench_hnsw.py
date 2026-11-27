"""Benchmark the hand-written HNSW (src/whyfinder/rag/hnsw.py) against hnswlib (FR-15).

Two datasets: the demo's review quotes as LSA vectors (5,800 indexed, 200 held out as queries) and
10,000 random unit vectors in 32 dimensions (200 random queries). With `--corpus`, a third alone:
sentences from the full review corpus (the parse stage's review_text.parquet), sampled with the
seed and embedded with the same LSA, to see whether the hand-written graph holds up at a size
17 times the demo's index. Both libraries get M = 16, efConstruction = 200, inner product, one
thread. Reported per efSearch: recall@10 against exact search and queries per second; per
library: build seconds.

    uv run --with hnswlib python scripts/bench_hnsw.py --out bench.json
    uv run --with hnswlib python scripts/bench_hnsw.py --corpus data/interim/review_text.parquet
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from whyfinder.params import load_params  # noqa: E402
from whyfinder.rag.hnsw import build, exact  # noqa: E402
from whyfinder.rag.lsa import fit  # noqa: E402
from whyfinder.rag.text import tokenize  # noqa: E402

EFS = (16, 32, 64, 128)
K = 10


def quotes(seed: int) -> tuple[np.ndarray, np.ndarray]:
    games = json.loads((ROOT / "web/public/data/reviews.json").read_text())["games"]
    texts = [q["text"] for key in sorted(games, key=int) for q in games[key]["quotes"]]
    tokens = [tokenize(t) for t in texts]
    p = load_params()["rag"]["lsa"]
    vectors = fit(tokens, dim=int(p["dim"]), min_df=int(p["min_df"]), seed=seed).embed(tokens)
    vectors = vectors[np.linalg.norm(vectors, axis=1) > 0]
    order = np.random.default_rng(seed).permutation(len(vectors))
    return vectors[order[200:]], vectors[order[:200]]


def corpus(path: Path, n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """`n` + 200 distinct sentences of 6 to 40 words from the review corpus, as LSA vectors; the
    first 200 of a seeded order are the queries."""
    import re

    import pandas as pd

    texts = pd.read_parquet(path, columns=["text"])["text"].dropna().astype(str)
    rng = np.random.default_rng(seed)
    want = n + 200
    seen: set[str] = set()
    picked: list[str] = []
    for i in rng.permutation(len(texts)):
        for s in re.split(r"(?<=[.!?])\s+|\n+", texts.iat[int(i)]):
            s = " ".join(s.split())
            if 6 <= len(s.split()) <= 40 and s not in seen:
                seen.add(s)
                picked.append(s)
                break
        if len(picked) == want:
            break
    tokens = [tokenize(s) for s in picked]
    p = load_params()["rag"]["lsa"]
    vectors = fit(tokens, dim=int(p["dim"]), min_df=int(p["min_df"]), seed=seed).embed(tokens)
    vectors = vectors[np.linalg.norm(vectors, axis=1) > 0]
    order = rng.permutation(len(vectors))
    return vectors[order[200:]], vectors[order[:200]]


def random_unit(seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((10_200, 32))
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    return X[200:], X[:200]


def recall(found: list[list[int]], data: np.ndarray, queries: np.ndarray) -> float:
    hits = [
        len(set(f) & {i for i, _ in exact(data, q, K)}) / K
        for f, q in zip(found, queries, strict=True)
    ]
    return float(np.mean(hits))


def ours(data: np.ndarray, queries: np.ndarray, seed: int) -> dict[str, Any]:
    t = time.perf_counter()
    index = build(data, m=16, ef_construction=200, seed=seed)
    out: dict[str, Any] = {"build_s": time.perf_counter() - t, "ef": {}}
    for ef in EFS:
        t = time.perf_counter()
        found = [[i for i, _ in index.search(q, K, ef=ef)] for q in queries]
        qps = len(queries) / (time.perf_counter() - t)
        out["ef"][ef] = {"recall_at_10": recall(found, data, queries), "qps": qps}
    return out


def reference(data: np.ndarray, queries: np.ndarray, seed: int) -> dict[str, Any]:
    import hnswlib

    index = hnswlib.Index(space="ip", dim=data.shape[1])
    index.set_num_threads(1)
    t = time.perf_counter()
    index.init_index(max_elements=len(data), ef_construction=200, M=16, random_seed=seed)
    index.add_items(data.astype(np.float32), np.arange(len(data)))
    out: dict[str, Any] = {"build_s": time.perf_counter() - t, "ef": {}}
    for ef in EFS:
        index.set_ef(max(ef, K))
        t = time.perf_counter()
        found = [index.knn_query(q.astype(np.float32), k=K)[0][0].tolist() for q in queries]
        qps = len(queries) / (time.perf_counter() - t)
        out["ef"][ef] = {"recall_at_10": recall(found, data, queries), "qps": qps}
    return out


def table(name: str, n: int, dim: int, a: dict[str, Any], b: dict[str, Any]) -> str:
    lines = [
        f"### {name} ({n:,} vectors, {dim} dimensions, 200 queries)",
        "",
        f"Build: Whyfinder {a['build_s']:.1f} s, hnswlib {b['build_s']:.2f} s.",
        "",
        "| efSearch | recall@10, ours | recall@10, hnswlib | QPS, ours | QPS, hnswlib |",
        "| --- | --- | --- | --- | --- |",
    ]
    for ef in EFS:
        x, y = a["ef"][ef], b["ef"][ef]
        lines.append(
            f"| {ef} | {x['recall_at_10']:.3f} | {y['recall_at_10']:.3f} "
            f"| {x['qps']:,.0f} | {y['qps']:,.0f} |"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("bench.json"))
    ap.add_argument("--seed", type=int, default=20261117)
    ap.add_argument("--corpus", type=Path, help="review_text.parquet: run the corpus set alone")
    ap.add_argument("--corpus-n", type=int, default=100_000)
    a = ap.parse_args()
    results: dict[str, Any] = {}
    sections = []
    sets: tuple[tuple[str, Any], ...] = (
        ("Review quotes, LSA", quotes),
        ("Random unit vectors", random_unit),
    )
    if a.corpus is not None:
        path, n = a.corpus, a.corpus_n
        sets = (("Review sentences from the full corpus, LSA", lambda s: corpus(path, n, s)),)
    for name, make in sets:
        data, queries = make(a.seed)
        mine, theirs = ours(data, queries, a.seed), reference(data, queries, a.seed)
        results[name] = {"n": len(data), "dim": data.shape[1], "whyfinder": mine, "hnswlib": theirs}
        sections.append(table(name, len(data), data.shape[1], mine, theirs))
    a.out.write_text(json.dumps(results, indent=2) + "\n")
    print("\n\n".join(sections))
    return 0


if __name__ == "__main__":
    sys.exit(main())
