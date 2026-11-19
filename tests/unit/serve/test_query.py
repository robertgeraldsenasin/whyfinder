"""The API's query parser agrees with the demo's (web/src/lib/query.ts) on the shared cases."""

from __future__ import annotations

import json

import pytest

from tests.unit.serve.conftest import ROOT
from whyfinder.serve.model import ServedModel
from whyfinder.serve.query import clauses, find_game, fold, parse_query

CASES = json.loads((ROOT / "web" / "src" / "lib" / "__fixtures__" / "queries.json").read_text())


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["text"] or "empty")
def test_reads_each_shared_case_like_the_demo(served: ServedModel, case: dict[str, object]) -> None:
    q = parse_query(str(case["text"]), served.games)
    assert [served.title(i) for i in q.anchors] == case["anchors"]
    assert q.tags == case["tags"]
    assert q.max_price == case["max_price"]
    assert (q.year_min, q.year_max) == (case["year_min"], case["year_max"])
    assert q.unresolved == case["unresolved"]


def test_titles_with_separators_stay_whole(served: ServedModel) -> None:
    assert clauses("like Papers, Please, horror", served.games) == ["like Papers, Please", "horror"]


def test_find_game_prefers_exact_then_prefix_and_ignores_tiny_phrases(
    served: ServedModel, by_title: dict[str, int]
) -> None:
    assert find_game("portal 2", served.games) == by_title["Portal 2"]
    assert find_game("x", served.games) is None
    assert find_game("zzzyzzx quest", served.games) is None
    assert fold("Co-op") == fold("co op") == "coop"
    assert fold("Pokémon") == "pokemon"


def test_a_repeated_anchor_or_tag_is_kept_once(
    served: ServedModel, by_title: dict[str, int]
) -> None:
    q = parse_query("like Portal 2, Portal 2, co-op, coop", served.games)
    assert q.anchors == [by_title["Portal 2"]]
    assert q.tags == ["Co-op"]
