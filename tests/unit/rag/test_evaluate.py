"""The faithfulness report (06_RAG, "Evaluation")."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.unit.rag.test_generate import BAD, GOOD, PACK, SOURCE
from whyfinder.rag.claims import AttributionRef, Claim
from whyfinder.rag.evaluate import Case, cited_order, kendall_tau, reason_kind, run
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
