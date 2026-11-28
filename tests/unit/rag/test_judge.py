"""Entailment labels from a judge model (06_RAG, "Evaluation")."""

from __future__ import annotations

import json
from typing import Any

from tests.unit.rag.test_generate import PACK, QUOTE
from whyfinder.rag.claims import AttributionRef, Claim
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


def test_the_premise_states_every_fact_plainly_with_the_context() -> None:
    assert premise(PACK, facts(PACK)).splitlines() == [
        "The recommended game is Hades.",
        "The biggest reason for recommending Hades is that the player liked Dead Cells.",
        "50% of the reasons for recommending Hades came from the player liking Dead Cells.",
        "30% of the reasons for recommending Hades came from the player liking Hollow Knight.",
        "20% of the reasons for recommending Hades came from the player liking Celeste.",
        "Had the player not liked Dead Cells, Hades would not have been recommended.",
        f"A player of Hades, on combat: \u201c{QUOTE}\u201d.",
        "Hades shares the tag Roguelite with Dead Cells.",
    ]


def test_an_nli_judge_gets_the_pair_not_the_prompt() -> None:
    class Nli(Says):
        model = "nli:some/cross-encoder"

    judge = Nli(json.dumps({"label": "entailed"}))
    assert label(judge, "Facts here.", "A sentence.", seed=3) == "entailed"
    pair, _, _ = judge.calls[0]
    assert json.loads(pair) == ["Facts here.", "A sentence."]


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
    assert "30% of the reasons for recommending Hades" in judge.calls[1][0]
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
