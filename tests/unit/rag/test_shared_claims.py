"""The checker, the facts and the template agree with the demo's (web/src/lib/words.ts) on the
shared cases in web/src/lib/__fixtures__/claims.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from whyfinder.rag.claims import (
    AttributionRef,
    Claim,
    CounterfactualRef,
    Evidence,
    ReviewRef,
    Source,
    check,
)
from whyfinder.rag.generate import Pack, facts, template

ROOT = Path(__file__).resolve().parents[3]
SHARED = json.loads((ROOT / "web" / "src" / "lib" / "__fixtures__" / "claims.json").read_text())


def evidence(raw: dict[str, Any]) -> Evidence:
    if raw["type"] == "attribution":
        return AttributionRef(raw["game_id"], raw["share"])
    if raw["type"] == "review":
        return ReviewRef(raw["chunk_id"], raw["quote"])
    return CounterfactualRef(tuple(raw["removed_game_ids"]))


def raw(e: Evidence) -> dict[str, Any]:
    if isinstance(e, AttributionRef):
        return {"type": "attribution", "game_id": e.game_id, "share": e.share}
    if isinstance(e, ReviewRef):
        return {"type": "review", "chunk_id": e.chunk_id, "quote": e.quote}
    return {"type": "counterfactual", "removed_game_ids": list(e.removed_game_ids)}


def source() -> Source:
    s = SHARED["source"]
    return Source(
        pick_title=s["pick_title"],
        attributions={gid: (title, share) for gid, title, share in s["attributions"]},
        chunks=s["chunks"],
        removed=frozenset(s["removed"]),
        catalogue=tuple(s["catalogue"]),
    )


def pack(p: dict[str, Any]) -> Pack:
    return Pack(
        pick_title=p["pick_title"],
        liked=tuple((gid, title) for gid, title, _ in p["attributions"]),
        attributions=tuple((gid, title, share) for gid, title, share in p["attributions"]),
        removed=tuple((gid, title) for gid, title in p["removed"]),
        paths=(),
        kept_for_variety=False,
        quotes=tuple((cid, aspect, text) for cid, aspect, text in p["quotes"]),
    )


@pytest.mark.parametrize("case", SHARED["cases"], ids=lambda c: c["name"])
def test_the_checker_gives_the_shared_reasons(case: dict[str, Any]) -> None:
    claims = [Claim(c["text"], tuple(evidence(e) for e in c["evidence"])) for c in case["claims"]]
    assert check(claims, source()) == case["reasons"]


@pytest.mark.parametrize("case", SHARED["packs"], ids=lambda c: c["name"])
def test_facts_and_template_match_the_shared_cases(case: dict[str, Any]) -> None:
    p = pack(case["pack"])
    assert [[f.id, f.line] for f in facts(p)] == case["facts"]
    built = [{"text": c.text, "evidence": [raw(e) for e in c.evidence]} for c in template(p)]
    assert built == case["template"]


def test_the_shared_cases_cover_passes_and_every_kind_of_failure() -> None:
    reasons = [r for c in SHARED["cases"] for r in c["reasons"]]
    assert any(not c["reasons"] for c in SHARED["cases"])
    for start in (
        "more than",
        "no evidence",
        "names a game outside",
        "cites a game that is not among",
        "wrong share",
        "cites Portal 2 without",
        "cites a review chunk not retrieved",
        "the quote is not a verbatim",
        "the sentence does not carry",
        "the counterfactual set is not",
    ):
        assert any(r.startswith(start) for r in reasons), start
    assert any(r.endswith("matches no cited share") for r in reasons)
    assert any(r.endswith("the limit is 60") for r in reasons)
