"""The review index (06_RAG): chunks keep their words; search fuses BM25 and dense rankings."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from whyfinder.params import load_params
from whyfinder.rag.reviews import build, is_verbatim, split

QUOTES = {
    "620": [
        "It weaves puzzles and story together beautifully.",
        "Great co-op puzzles to solve with a friend.",
        "Funny writing and memorable characters.",
    ],
    "440": [
        "Chaotic online co-op fun with nine classes.",
        "Hats, trading and a lot of chaos.",
    ],
    "8980": [
        "Loot, guns and co-op with friends.",
        "The story is thin but the shooting is fun.",
    ],
    "999": ["A game outside the catalogue."],
}
IDS = [620, 440, 8980]


def export() -> dict[str, Any]:
    return {
        gid: {"quotes": [{"text": q, "hours": 1.5, "year": 2016} for q in quotes], "terms": []}
        for gid, quotes in QUOTES.items()
    }


@pytest.fixture(scope="module")
def index():  # type: ignore[no-untyped-def]
    p = load_params()["rag"]
    small = {**p, "lsa": {"dim": 4, "min_df": 1}, "hnsw": {**p["hnsw"], "ef_construction": 20}}
    return build(export(), IDS, small, seed=1)


def test_chunks_keep_their_words_and_skip_unknown_games(index) -> None:  # type: ignore[no-untyped-def]
    assert len(index.chunks) == 7
    assert index.chunks[0].chunk_id == "c_440_0"
    assert {c.game for c in index.chunks} == {0, 1, 2}
    texts = {c.text for c in index.chunks}
    assert "Great co-op puzzles to solve with a friend." in texts
    assert "A game outside the catalogue." not in texts
    assert np.allclose(np.linalg.norm(index.vectors, axis=1), 1.0)


def test_search_within_one_game_returns_only_its_chunks(index) -> None:  # type: ignore[no-untyped-def]
    hits = index.search("puzzles", 3, game=0)
    assert hits
    assert {index.chunks[h.chunk].game for h in hits} == {0}
    assert hits[0].bm25_rank == 1
    assert index.search("puzzles", 3, game=99) == []


def test_search_across_games_fuses_both_rankings(index) -> None:  # type: ignore[no-untyped-def]
    hits = index.search("co-op friends", 3)
    assert len(hits) == 3
    assert all(h.bm25_rank is not None or h.dense_rank is not None for h in hits)
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
    assert index.search("", 3) == []
    assert index.search("the and of", 3) == []
    assert index.search("co-op", 0) == []


def test_long_reviews_are_split_in_their_own_words() -> None:
    text = " ".join(f"w{i}" for i in range(30))
    parts = split(text, size=10, overlap=2)
    assert parts[0] == " ".join(f"w{i}" for i in range(10))
    assert parts[1].startswith("w8 w9")
    assert split("  spaced   out  ", 10, 2) == ["spaced out"]


def test_verbatim_quotes_are_spans_of_at_most_25_words() -> None:
    text = "Tight, fast combat and a soundtrack that never lets up."
    assert is_verbatim("fast combat", text)
    assert is_verbatim(text, text)
    assert not is_verbatim("fast, tight combat", text)
    assert not is_verbatim("", text)
    long_text = " ".join(["word"] * 30)
    assert not is_verbatim(long_text, long_text)


def test_an_export_without_text_is_rejected() -> None:
    with pytest.raises(ValueError, match="no review text"):
        build({"620": {"quotes": []}}, IDS, load_params()["rag"], seed=1)
