"""How faithful the generated explanations are (docs/spec/06_RAG.md, "Evaluation").

For each case (one pick with its facts) the model answers twice: with the facts, through the same
generate-check-retry-fallback path the API uses, and once without the attributions (the research
ablation). Reported:

- **claim support before fallback**: the share of the model's first-attempt claims that pass the
  checker on their own (pass mark 95%), and of outputs that pass whole on the first or second try;
- **fallback rate**: outputs replaced by the template sentences;
- **attribution agreement**: Kendall's τ between the order the model names liked games and their
  attribution order (pass mark 0.7), over outputs naming at least two;
- **ablation**: how often the first liked game named is the real top contributor, with the facts and
  without the shares.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from whyfinder.rag.claims import AttributionRef, Claim, Source, check
from whyfinder.rag.generate import Backend, Outcome, Pack, attempt, explain, prompt


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


def named_order(claims: Sequence[Claim], source: Source) -> list[str]:
    """Liked games (by ID) in the order the claims first name them, by title in the text."""
    titles = {gid: title for gid, (title, _) in source.attributions.items()}
    seen: list[tuple[int, int, str]] = []
    text = " ".join(c.text for c in claims)
    for n, (gid, title) in enumerate(titles.items()):
        at = text.find(title)
        if at >= 0:
            seen.append((at, n, gid))
    return [gid for _, _, gid in sorted(seen)]


def cited_order(claims: Sequence[Claim]) -> list[str]:
    """Liked games in the order the claims cite them as attribution evidence."""
    out: list[str] = []
    for claim in claims:
        for e in claim.evidence:
            if isinstance(e, AttributionRef) and e.game_id not in out:
                out.append(e.game_id)
    return out


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


def run(cases: Sequence[Case], backend: Backend, *, seed: int) -> dict[str, Any]:
    outcomes: list[Outcome] = []
    first_claims = first_supported = 0
    kinds: Counter[str] = Counter()
    taus: list[float] = []
    top1 = top1_ablation = 0
    for case in cases:
        out = explain(case.pack, case.source, backend, case.template, seed=seed)
        outcomes.append(out)
        first = out.attempts[0]
        first_claims += len(first.claims)
        first_supported += sum(1 for c in first.claims if not check([c], case.source))
        kinds.update(reason_kind(r) for r in first.reasons)
        truth = list(case.source.attributions)
        model_claims = [] if out.fallback_used else out.claims
        order = named_order(model_claims, case.source)
        if len(order) >= 2:
            taus.append(kendall_tau(order, truth))
        if order and order[0] == truth[0]:
            top1 += 1
        blind = attempt(
            backend.complete(prompt(case.pack, with_attributions=False), seed=seed), case.source
        )
        guess = cited_order(blind.claims) or named_order(blind.claims, case.source)
        if guess and guess[0] == truth[0]:
            top1_ablation += 1
    n = len(cases)
    used = Counter(o.used for o in outcomes)
    return {
        "cases": n,
        "model": backend.model,
        "digest": backend.digest,
        "seed": seed,
        "claim_support_before_fallback": first_supported / first_claims if first_claims else None,
        "first_try_pass_rate": used["model"] / n if n else None,
        "pass_within_two_tries": (used["model"] + used["model-retry"]) / n if n else None,
        "fallback_rate": used["template"] / n if n else None,
        "attribution_agreement_tau": sum(taus) / len(taus) if taus else None,
        "attribution_agreement_outputs": len(taus),
        "top1_named_with_attributions": top1 / n if n else None,
        "top1_named_without_attributions": top1_ablation / n if n else None,
        "first_try_rejections": dict(sorted(kinds.items())),
    }
