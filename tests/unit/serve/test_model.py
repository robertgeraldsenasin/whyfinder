"""The served model: filters, histories, search, and runs with and without diversity."""

from __future__ import annotations

from typing import Any

import pytest

from tests.unit.serve.conftest import PARAMS, REVIEWS, SLICE
from whyfinder.serve.model import Filters, ServedModel


def game(**over: Any) -> dict[str, Any]:
    return {"title": "Test", "tags": ["Co-op", "Indie"], "price": 9.99, "year": 2015, **over}


def test_filters_pass_only_games_that_meet_every_one() -> None:
    f = Filters(tags=("Co-op",), max_price=10.0, year_min=2010, year_max=2016)
    assert f.active
    assert f.passes(game())
    assert not f.passes(game(tags=["Indie"]))
    assert not f.passes(game(price=19.99))
    assert not f.passes(game(year=2009))
    assert not f.passes(game(year=2017))


def test_unknown_price_or_year_fails_a_filter_on_it() -> None:
    assert not Filters(max_price=10.0).passes(game(price=None))
    assert not Filters(year_min=2010).passes(game(year=None))
    assert Filters(tags=("Co-op",)).passes(game(price=None, year=None))
    assert not Filters().active
    assert Filters().passes(game(tags=None, price=None, year=None))


def test_history_keeps_known_games_in_order_once(served: ServedModel) -> None:
    a, b = served.ids[3], served.ids[1]
    known, unknown = served.history([a, 999_999_999, b, a])
    assert [i for i, _ in known] == [3, 1]
    assert all(w == served.weight for _, w in known)
    assert unknown == [999_999_999]


def test_without_diversity_the_picks_are_the_relevance_top(served: ServedModel) -> None:
    history, _ = served.history(served.ids[:3])
    plain = served.run(history, k=10, filters=Filters(), diversity=False)
    diverse = served.run(history, k=10, filters=Filters(), diversity=True)
    assert plain.picks == diverse.relevance_top
    assert plain.variety == [False] * len(plain.picks)


def test_a_filter_nothing_meets_gives_no_picks(served: ServedModel) -> None:
    history, _ = served.history(served.ids[:3])
    rec = served.run(history, k=10, filters=Filters(year_min=2020, year_max=2010), diversity=True)
    assert rec.picks == []


def test_explaining_a_game_outside_the_picks(served: ServedModel) -> None:
    history, _ = served.history(served.ids[:3])
    rec = served.run(history, k=10, filters=Filters(), diversity=True)
    outside = next(i for i in range(len(served.ids)) if i not in rec.picks and i > 2)
    e = served.explain(history, outside, filters=Filters())
    assert e.rank is None
    assert e.counterfactual.removed == []
    assert not e.kept_for_variety
    assert sum(c.total for c in e.contributions) == pytest.approx(e.score, abs=1e-9)


def test_search_puts_prefix_matches_first_and_respects_the_limit(served: ServedModel) -> None:
    hits = [served.title(i) for i in served.search("dark", limit=3)]
    assert len(hits) == 3
    assert all(h.lower().startswith("dark") for h in hits)
    assert served.search("   ") == []
    assert served.search("zzzyzzx") == []


def test_load_records_hashes_and_the_data_version(served: ServedModel, full: ServedModel) -> None:
    assert set(served.hashes) == {SLICE.name, PARAMS.name}
    assert set(full.hashes) == {SLICE.name, PARAMS.name, REVIEWS.name}
    assert served.reviews is None
    assert full.reviews is not None
    assert all(len(h) == 64 for h in served.hashes.values())
    assert served.data_version.startswith("demo-slice v1")
    assert served.node_label(None) == ""


def test_aspects_are_shared_tags_then_shared_review_words(
    full: ServedModel, by_title: dict[str, int]
) -> None:
    tf2, portal2 = by_title["Team Fortress 2"], by_title["Portal 2"]
    aspects = full.aspects(tf2, portal2, limit=10)
    tags = set(full.games[tf2]["tags"]) & set(full.games[portal2]["tags"])
    head = [a for a in aspects if a in tags]
    assert aspects[: len(head)] == head
    assert set(aspects[len(head) :]) <= set(full.terms[tf2]) & set(full.terms[portal2])
    assert full.aspects(tf2, portal2, limit=2) == aspects[:2]
