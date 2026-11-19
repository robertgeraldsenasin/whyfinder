"""Claims (FR-16) and the claim checker (FR-17)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whyfinder.rag.claims import (
    SCHEMA,
    AttributionRef,
    Claim,
    CounterfactualRef,
    ReviewRef,
    SchemaError,
    Source,
    check,
    dump,
    parse,
)

ROOT = Path(__file__).resolve().parents[3]
QUOTE_TEXT = "Tight, fast combat and a soundtrack that never lets up."
SOURCE = Source(
    pick_title="Hades",
    attributions={
        "1": ("Dead Cells", 0.42),
        "2": ("Hollow Knight", 0.30),
        "3": ("Celeste", 0.12),
        "4": ("Bastion", 0.08),
        "5": ("Transistor", 0.05),
        "6": ("Spelunky", 0.03),
    },
    chunks={"c_7_0": QUOTE_TEXT},
    removed=frozenset({"1", "2"}),
    catalogue=("Dead Cells", "Hollow Knight", "Celeste", "Dota 2", "Hades", "Spelunky"),
)


def attribution(text: str, game_id: str = "1", share: float = 0.42) -> Claim:
    return Claim(text, (AttributionRef(game_id, share),))


def test_the_committed_schema_matches_the_code() -> None:
    committed = json.loads((ROOT / "docs" / "spec" / "claim.schema.json").read_text())
    assert committed == SCHEMA


def test_parse_and_dump_round_trip() -> None:
    claims = [
        attribution("Dead Cells drives this pick (42%)."),
        Claim(f'Players say "{QUOTE_TEXT}"', (ReviewRef("c_7_0", QUOTE_TEXT),)),
        Claim(
            "Without Dead Cells and Hollow Knight it drops out.", (CounterfactualRef(("1", "2")),)
        ),
    ]
    assert parse(json.dumps(dump(claims))) == claims


def test_dumped_claims_validate_against_the_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    doc = dump([attribution("Dead Cells drives it."), Claim("x", (CounterfactualRef(("1",)),))])
    jsonschema.validate(doc, SCHEMA)


def doc(text: object, *evidence: object) -> str:
    return json.dumps({"claims": [{"text": text, "evidence": list(evidence)}]})


ATTR = {"type": "attribution", "game_id": "1", "share": 0.42}


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        '{"claims": [], "extra": 1}',
        '{"claims": [{"text": "x"}]}',
        doc("", ATTR),
        doc("x"),
        doc("x", {**ATTR, "game_id": 1}),
        doc("x", {**ATTR, "share": True}),
        doc("x", {"type": "review", "chunk_id": "c", "quote": ""}),
        doc("x", {"type": "counterfactual", "removed_game_ids": []}),
        doc("x", {"type": "vibes"}),
        doc("x", "1"),
        json.dumps({"claims": [{"text": f"c{i}", "evidence": [ATTR]} for i in range(4)]}),
    ],
)
def test_parse_rejects_what_the_schema_rejects(raw: str) -> None:
    with pytest.raises(SchemaError):
        parse(raw)
    jsonschema = pytest.importorskip("jsonschema")
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        return
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, SCHEMA)


def test_faithful_claims_pass() -> None:
    claims = [
        attribution("Dead Cells is the biggest driver of this pick (42%)."),
        Claim("Hollow Knight adds about 30%.", (AttributionRef("2", 0.30),)),
        Claim(f'Players of Hades say "{QUOTE_TEXT}"', (ReviewRef("c_7_0", QUOTE_TEXT),)),
    ]
    assert check(claims, SOURCE) == []
    assert check([attribution("Dead Cells drives it (41.6%).")], SOURCE) == []
    cf = Claim(
        "Remove Dead Cells and Hollow Knight and Hades drops out.", (CounterfactualRef(("2", "1")),)
    )
    assert check([cf], SOURCE) == []


@pytest.mark.parametrize(
    ("claim", "reason"),
    [
        (attribution("Spelunky matters.", game_id="6", share=0.03), "not among the top 5"),
        (attribution("Dead Cells drives it.", share=0.5), "wrong share"),
        (attribution("It drives it."), "without naming it"),
        (attribution("Dead Cells drives 55% of it."), "matches no cited share"),
        (attribution("Dead Cells drives it, like Dota 2."), "outside the pick and the history"),
        (Claim('They say "fast combat"', (ReviewRef("c_9_9", "fast combat"),)), "not retrieved"),
        (
            Claim('They say "fast, tight combat"', (ReviewRef("c_7_0", "fast, tight combat"),)),
            "verbatim",
        ),
        (Claim("They like the combat.", (ReviewRef("c_7_0", "fast combat"),)), "carry its quote"),
        (Claim("Without Dead Cells it drops.", (CounterfactualRef(("1",)),)), "counterfactual set"),
        (Claim("Trust me.", ()), "no evidence"),
    ],
)
def test_each_rule_rejects_its_failure(claim: Claim, reason: str) -> None:
    reasons = check([claim], SOURCE)
    assert reasons
    assert any(reason in r for r in reasons), reasons


def test_quotes_may_name_other_games_and_count_toward_nothing_else() -> None:
    text = "Better than Dota 2 at 99% of things."
    source = Source(**{**SOURCE.__dict__, "chunks": {"c_7_1": text}})
    claim = Claim(f'A player writes "{text}"', (ReviewRef("c_7_1", text),))
    assert check([claim], source) == []


def test_limits_on_claims_and_words() -> None:
    many = [attribution("Dead Cells drives it.") for _ in range(4)]
    assert any("more than 3 claims" in r for r in check(many, SOURCE))
    long_text = "Dead Cells " + "really " * 60 + "drives it."
    assert any("the limit is 60" in r for r in check([attribution(long_text)], SOURCE))
