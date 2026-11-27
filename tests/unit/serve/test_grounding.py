"""Queries, rows and rankings for hand-labelling review retrieval (#33)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from whyfinder.serve.grounding import label_queries, label_rankings, label_rows
from whyfinder.serve.model import ServedModel


def test_label_queries_are_distinct_seeded_and_come_with_every_review(full: ServedModel) -> None:
    picked = label_queries(full, 12, seed=7)
    assert len(picked) == len(set(picked)) == 12
    assert label_queries(full, 12, seed=7) == picked
    assert label_queries(full, 12, seed=8) != picked
    rows = label_rows(full, picked)
    assert full.reviews is not None
    for number, (pick, aspect) in enumerate(picked, start=1):
        mine = [r for r in rows if r.query == number]
        assert {r.aspect for r in mine} == {aspect}
        assert len(mine) == len(full.reviews.by_game[pick])
        assert [r.chunk_id for r in mine] == sorted(
            (r.chunk_id for r in mine), key=lambda c: int(c.rsplit("_", 1)[1])
        )
        assert all(r.label_a is None and r.label_b is None for r in mine)
    ranked = label_rankings(full, rows)
    assert set(ranked) == {"bm25", "dense", "rrf"}
    first = [r for r in rows if r.query == 1]
    hits = full.reviews.search(first[0].aspect, 5, game=picked[0][0])
    assert ranked["rrf"][1][:5] == [full.reviews.chunks[h.chunk].chunk_id for h in hits]
    assert set(ranked["bm25"][1]) <= {r.chunk_id for r in first}


def test_labelling_needs_the_review_index(served: ServedModel) -> None:
    with pytest.raises(ValueError, match="review index"):
        label_queries(served, 3, seed=1)
    with pytest.raises(ValueError, match="review index"):
        label_rows(served, [])
    with pytest.raises(ValueError, match="review index"):
        label_rankings(served, [])
