"""The faithfulness report (06_RAG, "Evaluation")."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.unit.rag.test_generate import BAD, GOOD, PACK, SOURCE
from whyfinder.rag.claims import AttributionRef, Claim
from whyfinder.rag.evaluate import (
    Case,
    cited_order,
    kendall_tau,
    parroted,
    reason_kind,
    run,
    unfinished,
)
from whyfinder.rag.generate import template


def test_kendall_tau_against_hand_counts() -> None:
    truth = ["a", "b", "c", "d"]
    assert kendall_tau(["a", "b", "c"], truth) == 1.0
    assert kendall_tau(["c", "b", "a"], truth) == -1.0
    assert kendall_tau(["a", "c", "b"], truth) == pytest.approx(1 / 3)
    with pytest.raises(ValueError, match="two"):
        kendall_tau(["a"], truth)


def test_cited_order() -> None:
    claims = [
        Claim("Hollow Knight and then Dead Cells.", (AttributionRef("1", 0.5),)),
        Claim("Celeste too.", (AttributionRef("2", 0.3), AttributionRef("1", 0.5))),
    ]
    assert cited_order(claims) == ["1", "2"]
    assert reason_kind("wrong share for X") == "wrong share"
    assert reason_kind("something new") == "other"


class Script:
    model = "script"
    digest = "sha256:script"

    def __init__(self, answers: dict[bool, list[str]]) -> None:
        self.answers = answers

    def complete(self, prompt: str, *, seed: int, schema: dict[str, Any]) -> str:
        blind = "L1:" in prompt
        return self.answers[blind].pop(0)


def test_the_report_counts_support_fallbacks_agreement_and_the_ablation() -> None:
    two = json.dumps(
        {
            "claims": [
                {"fact": "A1", "text": "Dead Cells drives it (50%)."},
                {"fact": "A2", "text": "Hollow Knight adds 30%."},
            ]
        }
    )
    guess = json.dumps({"claims": [{"fact": "L1", "text": "Celeste, probably."}]})
    backend = Script({False: [two, BAD, BAD, BAD, GOOD], True: [guess, guess, guess]})
    cases = [Case(PACK, SOURCE, lambda: template(PACK)) for _ in range(3)]
    report = run(cases, backend, seed=1)
    assert report["cases"] == 3
    assert report["first_try_pass_rate"] == pytest.approx(1 / 3)
    assert report["pass_within_two_tries"] == pytest.approx(2 / 3)
    assert report["fallback_rate"] == pytest.approx(1 / 3)
    assert report["claim_support_before_fallback"] == pytest.approx(2 / 4)
    assert report["attribution_agreement_tau"] == 1.0
    assert report["attribution_agreement_outputs"] == 1
    assert report["top1_cited_with_attributions"] == 1.0  # every first answer cites A1
    assert report["top1_cited_without_attributions"] == 0.0
    assert report["first_try_rejections"] == {
        "outside the pick and the history": 2,
        "without naming it": 2,
    }
    assert report["entailment"] == {}
    assert report["served_adds_nothing"] == 1.0  # "drives", "adds", "carries": one word each


class Judge:
    model = "judge"
    digest = "sha256:judge"

    def __init__(self, *labels: str) -> None:
        self.labels = list(labels)
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, seed: int, schema: dict[str, Any]) -> str:
        self.prompts.append(prompt)
        return json.dumps({"label": self.labels.pop(0)})


def test_the_judge_labels_served_model_sentences_and_the_template_as_a_control() -> None:
    two = json.dumps(
        {
            "claims": [
                {"fact": "A1", "text": "Dead Cells drives it (50%)."},
                {"fact": "A2", "text": "Hollow Knight adds 30%, and it is the best game ever."},
            ]
        }
    )
    guess = json.dumps({"claims": [{"fact": "L1", "text": "Celeste, probably."}]})
    backend = Script({False: [two, BAD, BAD], True: [guess, guess]})
    cases = [Case(PACK, SOURCE, lambda: template(PACK)) for _ in range(2)]
    n_template = len(template(PACK))
    # Case 1: two model sentences, then its template; case 2 falls back: only its template.
    judge = Judge(
        "entailed",
        "neutral",
        *["entailed"] * n_template,
        *["entailed"] * (n_template - 1),
        "neutral",
    )
    report = run(cases, backend, seed=1, judges=[judge])
    ent = report["entailment"]["judge"]
    assert ent["digest"] == "sha256:judge"
    assert ent["self_judged"] is False
    assert ent["served_model_sentences"] == {
        "sentences": 2,
        "entailed": 0.5,
        "neutral": 0.5,
        "contradicted": 0.0,
        "invalid": 0.0,
    }
    control = ent["template_sentences"]
    assert control["sentences"] == 2 * n_template
    assert control["neutral"] == pytest.approx(1 / (2 * n_template))
    facts_part = judge.prompts[0].split("Sentence:")[0]
    for line in (
        "The biggest reason for recommending Hades is that the player liked Dead Cells.",
        "50% of the reasons for recommending Hades came from the player liking Dead Cells.",
        "30% of the reasons for recommending Hades came from the player liking Hollow Knight.",
    ):
        assert line in facts_part


def test_a_sentence_that_only_rewords_its_fact_adds_nothing() -> None:
    from whyfinder.rag.evaluate import adds_nothing, known_text
    from whyfinder.rag.generate import facts

    a1 = facts(PACK)[0]
    known = known_text(PACK, a1)
    assert "Dead Cells, 50%" in known
    assert adds_nothing("Dead Cells supplied 50% of the reasons for Hades.", known)
    assert adds_nothing("You liked Dead Cells, which is 50% of why Hades was picked.", known)
    assert not adds_nothing(
        "Dead Cells gives half the reasons: both are fast roguelites with tight combat.", known
    )
    assert adds_nothing("Dead Cells, quickly.", known)  # one new word is allowed
    assert not adds_nothing("Dead Cells, quickly and brutally.", known)


def test_fluency_proxies() -> None:
    assert unfinished("Dead Cells counted for 50% of the score, making it ")
    assert unfinished("Dead Cells counted for 50% of the score, making it")
    assert unfinished("Dead Cells counted for 50% of the score,")
    assert not unfinished("Dead Cells counted for 50% of the score")
    assert not unfinished("Dead Cells counted for 50% of the score.")
    assert not unfinished("They say \u201cgreat\u201d")
    lines = ["Dead Cells counted for 50% of the score"]
    assert parroted("Dead Cells counted for 50% of the score.", lines)
    assert not parroted("You spent hours in Dead Cells, and it carries half of this pick.", lines)
