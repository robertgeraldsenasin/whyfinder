"""Tokens, chunks, BM25 against a naive reference (FR-14) and reciprocal rank fusion."""

from __future__ import annotations

import math

import numpy as np
import pytest

from whyfinder.rag.bm25 import build
from whyfinder.rag.fuse import rrf
from whyfinder.rag.text import chunk, fold, tokenize

DOCS = [
    "Tight, fast combat and a great soundtrack.",
    "The combat is slow but the story is great, great, great.",
    "Co-op with friends is the best part; solo is dull.",
    "A roguelike with tight controls and fast runs.",
    "",
    "Story story story: a long story-driven game with combat.",
]


def reference(docs: list[list[str]], query: list[str], k1: float, b: float) -> list[float]:
    """04_ALGORITHMS §A8 written out term by term, with no sharing of code with the index."""
    n = len(docs)
    avgdl = sum(len(d) for d in docs) / n
    out = []
    for d in docs:
        total = 0.0
        for term in query:
            df = sum(1 for other in docs if term in other)
            if df == 0:
                continue
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            tf = d.count(term)
            if tf == 0:
                continue
            total += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(d) / avgdl))
        out.append(total)
    return out


def test_tokens_are_folded_and_stop_words_dropped() -> None:
    curly = chr(0x2019)
    text = f"It{curly}s a Rogue-like with TIGHT combat; Pokémon fans won{curly}t mind."
    assert tokenize(text) == [
        "rogue",
        "tight",
        "combat",
        "pokemon",
        "fans",
        "mind",
    ]
    assert fold("Ça Va") == "ca va"
    assert tokenize("") == []


def test_chunks_overlap_and_cover_every_word() -> None:
    words = [str(i) for i in range(250)]
    parts = chunk(words, size=100, overlap=20)
    assert [len(p) for p in parts] == [100, 100, 90]
    assert parts[1][:20] == parts[0][-20:]
    assert parts[-1][-1] == "249"
    assert chunk(["a", "b"]) == [["a", "b"]]
    assert chunk([]) == []
    for bad in ((0, 0), (10, 10), (10, -1)):
        with pytest.raises(ValueError, match="overlap"):
            chunk(words, *bad)


@pytest.mark.parametrize(("k1", "b"), [(1.2, 0.75), (0.9, 0.4), (2.0, 1.0), (1.2, 0.0)])
@pytest.mark.parametrize(
    "query", ["tight fast combat", "story story", "co-op friends", "nothing here", "great"]
)
def test_bm25_matches_the_reference(query: str, k1: float, b: float) -> None:
    docs = [tokenize(d) for d in DOCS]
    q = tokenize(query)
    index = build(docs, k1=k1, b=b)
    assert np.allclose(index.scores(q), reference(docs, q, k1, b), atol=1e-12)


def test_bm25_top_ranks_positive_scores_with_ties_by_document() -> None:
    docs = [["a", "b"], ["a", "b"], ["c"], ["a"]]
    index = build(docs)
    top = index.top(["a", "b"], k=10)
    assert [d for d, _ in top] == [0, 1, 3]
    assert top[0][1] == top[1][1]
    assert index.top(["a"], k=10, among=np.array([2, 3])) == [(3, index.scores(["a"])[3])]
    assert index.top(["zzz"], k=5) == []
    assert build([]).scores(["a"]).size == 0


def test_bm25_rejects_bad_parameters_and_leaves_input_alone() -> None:
    docs = [["a", "a"], ["b"]]
    build(docs)
    assert docs == [["a", "a"], ["b"]]
    with pytest.raises(ValueError, match="k1"):
        build(docs, k1=-1.0)
    with pytest.raises(ValueError, match="k1"):
        build(docs, b=1.5)


def test_rrf_sums_reciprocal_ranks_with_ties_by_document() -> None:
    fused = rrf([[3, 1, 2], [1, 3, 9]], k=60)
    assert [d for d, _ in fused] == [1, 3, 2, 9]
    assert fused[0][1] == pytest.approx(1 / 62 + 1 / 61)
    assert fused[0][1] == fused[1][1]
    assert rrf([[5, 5, 4]]) == [(5, 1 / 61), (4, 1 / 63)]
    assert rrf([]) == []
    with pytest.raises(ValueError, match="non-negative"):
        rrf([[1]], k=-1)
