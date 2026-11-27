"""Entailment labels from a judge model (06_RAG, "Evaluation")."""

from __future__ import annotations

import json
from typing import Any

from tests.unit.rag.test_generate import PACK, QUOTE
from whyfinder.rag.claims import AttributionRef, Claim, CounterfactualRef, ReviewRef
from whyfinder.rag.generate import facts
from whyfinder.rag.judge import LABELS, SCHEMA, label, labels, premise, shares


class Says:
    model = "judge"
    digest = "sha256:judge"

    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, dict[str, Any], int]] = []

    def complete(self, prompt: str, *, seed: int, schema: dict[str, Any]) -> str:
        self.calls.append((prompt, schema, seed))
        return self.answers.pop(0)


def test_the_premise_holds_only_the_cited_facts_and_the_context() -> None:
    listed = facts(PACK)
    claim = Claim("Dead Cells is why.", (AttributionRef("1", 0.5),))
    text = premise(PACK, claim, listed)
    assert text.splitlines() == [
        "The recommended game is Hades.",
        "Dead Cells counted for 50% of the score.",
        "Hades shares the tag Roguelite with Dead Cells.",
    ]
    both = Claim("x", (CounterfactualRef(("1",)), ReviewRef("c_7_0", QUOTE)))
    lines = premise(PACK, both, listed).splitlines()
    assert lines[1] == "Without Dead Cells in the list, Hades would drop out of the picks."
    assert lines[2] == f"A player of Hades, on combat: “{QUOTE}”."
    assert premise(PACK, Claim("x", ()), listed).count("\n") == 1  # nothing cited


def test_the_judge_is_asked_for_one_label_and_anything_else_is_invalid() -> None:
    judge = Says(json.dumps({"label": "neutral"}), "not json", '{"label": "maybe"}', "[1]")
    assert label(judge, "Facts.", "A sentence.", seed=7) == "neutral"
    prompt, schema, seed = judge.calls[0]
    assert "Facts:\nFacts.\n" in prompt
    assert "Sentence: A sentence." in prompt
    assert schema == SCHEMA
    assert schema["properties"]["label"]["enum"] == list(LABELS)
    assert seed == 7
    assert [label(judge, "p", "s", seed=7) for _ in range(3)] == ["invalid"] * 3


def test_labels_and_shares() -> None:
    judge = Says(*(json.dumps({"label": x}) for x in ("entailed", "contradicted")))
    claims = [
        Claim("Dead Cells is why (50%).", (AttributionRef("1", 0.5),)),
        Claim("Hollow Knight is why (30%).", (AttributionRef("2", 0.3),)),
    ]
    got = labels(judge, PACK, claims, facts(PACK), seed=1)
    assert got == ["entailed", "contradicted"]
    assert "Hollow Knight counted for 30%" in judge.calls[1][0]
    assert shares(["entailed", "entailed", "neutral", "invalid"]) == {
        "sentences": 4,
        "entailed": 0.5,
        "neutral": 0.25,
        "contradicted": 0.0,
        "invalid": 0.25,
    }
    assert shares([]) == {
        "sentences": 0,
        "entailed": None,
        "neutral": None,
        "contradicted": None,
        "invalid": None,
    }
