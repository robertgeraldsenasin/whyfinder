"""How faithful the generated explanations are (docs/spec/06_RAG.md, "Evaluation").

For each case (one pick with its facts) the model answers twice: with the facts, through the same
generate-check-retry-fallback path the API uses, and once without the attributions (the research
ablation). Reported:

- **claim support before fallback**: the share of the model's first-attempt claims that pass the
  checker on their own (pass mark 95%), and of outputs that pass whole on the first or second try;
- **fallback rate**: outputs replaced by the template sentences;
- **attribution agreement**: Kendall's τ between the order the model cites liked games and their
  attribution order (pass mark 0.7), over first answers citing at least two;
- **ablation**: how often the first liked game cited is the real top contributor, with the facts and
  without the shares;
- **three plain-text proxies** over the model's claims that were served: the share cut off
  mid-way by a length limit, the share that copy a fact line back nearly word for word, and the
  share that add at most one content word to their fact (a restatement in other words). The
  checker guards faithfulness, not fluency; these say how much a model adds over the template;
- **entailment**, per judge (`judge.py`): the share of served model sentences the facts entail,
  leave neutral or contradict, next to the same judge's labels for the template sentences of the
  same picks as a control.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations
from typing import Any

from whyfinder.rag.claims import AttributionRef, Claim, Source, check
from whyfinder.rag.generate import Backend, Fact, Outcome, Pack, ask, explain, facts, headings
from whyfinder.rag.judge import labels, shares


@dataclass(frozen=True)
class Case:
    pack: Pack
    source: Source
    template: Callable[[], list[Claim]]


def kendall_tau(named: Sequence[str], truth: Sequence[str]) -> float:
    """τ between the order of `named` and their order in `truth` (each id once; all in truth)."""
    rank = {g: r for r, g in enumerate(truth)}
    pairs = list(combinations([rank[g] for g in named], 2))
    if not pairs:
        raise ValueError("need at least two ranked items")
    concordant = sum(1 for a, b in pairs if a < b)
    return (2 * concordant - len(pairs)) / len(pairs)


def cited_order(claims: Sequence[Claim]) -> list[str]:
    """Liked games in the order the claims cite them as attribution evidence."""
    out: list[str] = []
    for claim in claims:
        for e in claim.evidence:
            if isinstance(e, AttributionRef) and e.game_id not in out:
                out.append(e.game_id)
    return out


DANGLING = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "into",
        "is",
        "it",
        "its",
        "making",
        "of",
        "on",
        "or",
        "so",
        "that",
        "the",
        "their",
        "to",
        "which",
        "while",
        "with",
    }
)


def unfinished(text: str) -> bool:
    """The sentence was cut off mid-way by a length limit: it ends on a space, a comma or a word
    that cannot end a sentence ("making it", "and the")."""
    if not text or text != text.rstrip() or text.rstrip()[-1] in ",;:-(":
        return True
    words = text.rstrip(" .!?\u201d\"')").split()
    return not words or words[-1].lower() in DANGLING


def parroted(text: str, lines: Sequence[str], at: float = 0.85) -> bool:
    """The sentence is (nearly) a fact line copied back, adding nothing a template would not."""
    norm = text.lower().strip(" .")
    return any(SequenceMatcher(None, norm, line.lower()).ratio() >= at for line in lines)


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


FILLER = _words(
    """
    a an and are as at be because been but by can could did do does for from had has have here
    how if in into is it it's its just may might more most much no not of on one or since so
    that the their them then there these they this those through to too very was were what when
    which while who why will with would you you'd you'll you're you've your also
    game games player players play played liked like likes love loved enjoy enjoyed recommend
    recommended recommending recommendation pick picked reason reasons share score percent
    """
)
WORD = re.compile(r"[a-z0-9']+")


def adds_nothing(text: str, known: str, at: int = 1) -> bool:
    """The sentence says its fact over in other words: at most `at` content words that are in
    neither the fact as listed, its heading, nor the recommended game's title."""
    seen = set(WORD.findall(known.lower()))
    new = {w for w in WORD.findall(text.lower()) if w not in seen and w not in FILLER}
    return len(new) <= at


def known_text(pack: Pack, fact: Fact) -> str:
    """Everything a sentence about `fact` could repeat without adding anything."""
    return " ".join((fact.cue, fact.line, pack.pick_title, headings(pack.pick_title)[fact.id[0]]))


def reason_kind(reason: str) -> str:
    for kind in (
        "claim schema",
        "no claims",
        "not among the top",
        "wrong share",
        "without naming it",
        "matches no cited share",
        "outside the pick and the history",
        "not retrieved",
        "verbatim",
        "carry its quote",
        "counterfactual set",
        "more than",
        "the limit is",
        "no evidence",
    ):
        if kind in reason:
            return kind
    return "other"


def run(
    cases: Sequence[Case], backend: Backend, *, seed: int, judges: Sequence[Backend] = ()
) -> dict[str, Any]:
    """The faithfulness report over `cases`. Agreement and the ablation look at the model's first
    answer (what the model does), not at what was served after the fallback. Each judge labels the
    served model sentences and, as a control, the template sentences for entailment."""
    outcomes: list[Outcome] = []
    first_claims = first_supported = 0
    kinds: Counter[str] = Counter()
    taus: list[float] = []
    top1 = top1_blind = 0
    served = cut = copied = restated = 0
    judged: dict[str, list[str]] = {j.model: [] for j in judges}
    control: dict[str, list[str]] = {j.model: [] for j in judges}
    for case in cases:
        out = explain(case.pack, case.source, backend, case.template, seed=seed)
        outcomes.append(out)
        listed = facts(case.pack)
        if not out.fallback_used:
            lines = [f.line for f in listed]
            served += len(out.claims)
            cut += sum(1 for c in out.claims if unfinished(c.text))
            copied += sum(1 for c in out.claims if parroted(c.text, lines))
            by_evidence = {f.evidence: f for f in listed}
            restated += sum(
                1
                for c in out.claims
                if adds_nothing(c.text, known_text(case.pack, by_evidence[c.evidence[0]]))
            )
            for j in judges:
                judged[j.model].extend(labels(j, case.pack, out.claims, listed, seed=seed))
        for j in judges:
            control[j.model].extend(labels(j, case.pack, case.template(), listed, seed=seed))
        first = out.attempts[0]
        first_claims += len(first.claims)
        first_supported += sum(1 for c in first.claims if not check([c], case.source))
        kinds.update(reason_kind(r) for r in first.reasons)
        truth = list(case.source.attributions)
        order = cited_order(first.claims)
        if len(order) >= 2:
            taus.append(kendall_tau(order, truth))
        if order and order[0] == truth[0]:
            top1 += 1
        blind = ask(backend, case.pack, case.source, seed=seed, with_attributions=False)
        guess = cited_order(blind.claims)
        if guess and guess[0] == truth[0]:
            top1_blind += 1
    n = len(cases)
    used = Counter(o.used for o in outcomes)

    def share(k: int) -> float | None:
        return k / n if n else None

    entailment = {
        j.model: {
            "digest": j.digest,
            "self_judged": j.model == backend.model,
            "served_model_sentences": shares(judged[j.model]),
            "template_sentences": shares(control[j.model]),
        }
        for j in judges
    }
    return {
        "cases": n,
        "entailment": entailment,
        "model": backend.model,
        "digest": backend.digest,
        "seed": seed,
        "claim_support_before_fallback": first_supported / first_claims if first_claims else None,
        "first_try_pass_rate": share(used["model"]),
        "pass_within_two_tries": share(used["model"] + used["model-retry"]),
        "fallback_rate": share(used["template"]),
        "attribution_agreement_tau": sum(taus) / len(taus) if taus else None,
        "attribution_agreement_outputs": len(taus),
        "top1_cited_with_attributions": share(top1),
        "top1_cited_without_attributions": share(top1_blind),
        "first_try_rejections": dict(sorted(kinds.items())),
        "served_model_claims": served,
        "served_unfinished": cut / served if served else None,
        "served_parroted": copied / served if served else None,
        "served_adds_nothing": restated / served if served else None,
    }
