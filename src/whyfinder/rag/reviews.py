"""The review index: chunks of player reviews, searchable by BM25 and by LSA vectors in an HNSW
graph, the two rankings fused by RRF (docs/spec/06_RAG.md, "Corpus and index" and steps 2-3).

Chunks keep their original wording, so a quote taken from one is verbatim. A search can be limited
to one game's chunks (the metadata filter of step 3); within one game both rankings are exact.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from whyfinder.rag import bm25 as bm25_
from whyfinder.rag import hnsw as hnsw_
from whyfinder.rag import lsa as lsa_
from whyfinder.rag.claims import MAX_QUOTE_WORDS, is_verbatim
from whyfinder.rag.fuse import rrf
from whyfinder.rag.text import chunk, tokenize

__all__ = ["MAX_QUOTE_WORDS", "Chunk", "Hit", "ReviewIndex", "build", "is_verbatim", "split"]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    game: int  # catalogue index
    text: str
    hours: float
    year: int | None


@dataclass(frozen=True)
class Hit:
    chunk: int
    score: float  # RRF
    bm25_rank: int | None
    dense_rank: int | None


@dataclass(frozen=True)
class ReviewIndex:
    chunks: list[Chunk]
    bm25: bm25_.Bm25
    lsa: lsa_.Lsa
    vectors: np.ndarray
    graph: hnsw_.Hnsw
    by_game: dict[int, np.ndarray]
    ef_search: int = 64
    rrf_k: int = 60

    def rankings(
        self, query: str, *, game: int | None = None, depth: int = 100
    ) -> tuple[list[int], list[int]]:
        """The BM25 and the dense ranking of chunks for a query, before fusion; within one game
        both are exact, across the corpus the dense side comes from the HNSW graph."""
        tokens = tokenize(query)
        if not tokens:
            return [], []
        q = self.lsa.embed([tokens])[0]
        if game is not None:
            among = self.by_game.get(game, np.zeros(0, dtype=np.int64))
            lexical = [d for d, _ in self.bm25.top(tokens, depth, among)]
            dense: list[int] = []
            if q.any() and among.size:
                sims = self.vectors[among] @ q
                order = np.lexsort((among, -sims))
                dense = [int(among[i]) for i in order if sims[i] > 0.0][:depth]
            return lexical, dense
        lexical = [d for d, _ in self.bm25.top(tokens, depth)]
        found = self.graph.search(q, depth, ef=max(self.ef_search, depth)) if q.any() else []
        return lexical, [d for d, s in found if s > 0.0]

    def search(
        self, query: str, k: int = 5, *, game: int | None = None, depth: int = 100
    ) -> list[Hit]:
        """The k best chunks for a query, optionally within one game, fused by RRF."""
        if k < 1:
            return []
        lexical, dense = self.rankings(query, game=game, depth=depth)
        lex_rank = {d: r for r, d in enumerate(lexical, start=1)}
        dense_rank = {d: r for r, d in enumerate(dense, start=1)}
        return [
            Hit(chunk=d, score=s, bm25_rank=lex_rank.get(d), dense_rank=dense_rank.get(d))
            for d, s in rrf([lexical, dense], k=self.rrf_k)[:k]
        ]


def split(text: str, size: int, overlap: int) -> list[str]:
    """A review's chunks in its own words (whitespace normalised)."""
    return [" ".join(words) for words in chunk(text.split(), size=size, overlap=overlap)]


def build(
    games: Mapping[str, Mapping[str, Any]],
    game_ids: Sequence[int],
    p: Mapping[str, Any],
    *,
    seed: int,
) -> ReviewIndex:
    """Index the review export (`whyfinder export reviews`: games keyed by Steam app ID); games
    outside `game_ids` are skipped."""
    index_of = {int(gid): i for i, gid in enumerate(game_ids)}
    chunks: list[Chunk] = []
    for key in sorted(games, key=int):
        g = index_of.get(int(key))
        if g is None:
            continue
        n = 0
        for quote in games[key].get("quotes", []):
            for text in split(str(quote["text"]), int(p["chunk_words"]), int(p["chunk_overlap"])):
                year = quote.get("year")
                chunks.append(
                    Chunk(
                        chunk_id=f"c_{key}_{n}",
                        game=g,
                        text=text,
                        hours=float(quote.get("hours", 0.0)),
                        year=None if year is None else int(year),
                    )
                )
                n += 1
    if not chunks:
        raise ValueError("no review text to index")
    tokens = [tokenize(c.text) for c in chunks]
    lexical = bm25_.build(tokens, k1=float(p["bm25"]["k1"]), b=float(p["bm25"]["b"]))
    model = lsa_.fit(tokens, dim=int(p["lsa"]["dim"]), min_df=int(p["lsa"]["min_df"]), seed=seed)
    vectors = model.embed(tokens)
    h = p["hnsw"]
    graph = hnsw_.build(
        vectors, m=int(h["M"]), ef_construction=int(h["ef_construction"]), seed=seed
    )
    owners = np.array([c.game for c in chunks], dtype=np.int64)
    by_game = {int(g): np.flatnonzero(owners == g) for g in np.unique(owners)}
    return ReviewIndex(
        chunks=chunks,
        bm25=lexical,
        lsa=model,
        vectors=vectors,
        graph=graph,
        by_game=by_game,
        ef_search=int(h["ef_search"]),
        rrf_k=int(p["rrf_k"]),
    )
