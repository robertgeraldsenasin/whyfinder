"""Entailment of generated sentences, labelled by a second local model (06_RAG, "Evaluation").

The checker proves what it can parse in a sentence: titles, shares, quotes, the counterfactual
set. Whatever a model writes around them (why a share matters, what two games have in common)
passes unread. Here a judge model reads each sentence against every fact the model was given (so
"the biggest reason" can follow from the shares), plus the graph paths offered as context, and
labels it the way natural-language inference does:

- **entailed**: everything the sentence states follows from those facts; rewording is fine;
- **neutral**: it adds something the facts neither give nor contradict (an opinion of the game,
  a reason that is not there);
- **contradicted**: some part conflicts with them.

The template sentences go through the same judge as a control. They are entailed by construction,
so whatever share the judge labels otherwise is its own error, and the model's numbers should be
read next to it. A judge grading its own sentences is flagged. Judgments are cached under the same
key as generations and replayed in CI.

06_RAG first named an NLI cross-encoder for this. One was tried (DeBERTa-v3 trained on MNLI, run
46086701897): it labelled 91% of the template sentences neutral, so it cannot read facts of this
kind, and an instruct model is used instead (ADR-0009).
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any, Final

from whyfinder.rag.claims import AttributionRef, Claim, ReviewRef
from whyfinder.rag.generate import Backend, Fact, Pack

LABELS: Final = ("entailed", "neutral", "contradicted")
JUDGE_MODEL: Final = "qwen2.5:7b"

SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["label"],
    "properties": {"label": {"enum": list(LABELS)}},
}

PROMPT: Final = (
    "You check a sentence written from facts about a game recommendation.\n\n"
    "Facts:\n{premise}\n\n"
    "Sentence: {sentence}\n\n"
    "Label the sentence.\n"
    "entailed: everything it states follows from the facts. Rewording is fine.\n"
    "neutral: it states something the facts neither give nor contradict, such as an opinion of "
    "a game or a reason that is not in the facts.\n"
    "contradicted: some part of it conflicts with the facts.\n\n"
    'Answer with JSON only: {{"label": "..."}}\n'
)


def sentence_case(text: str) -> str:
    return text[:1].upper() + text[1:]


def statement(pick: str, f: Fact) -> str:
    """One fact as a plain sentence a judge can read without the prompt's headings."""
    e = f.evidence
    if isinstance(e, AttributionRef):
        title = f.cue.rsplit(", ", 1)[0]
        pct = round(e.share * 100)
        return f"{pct}% of the reasons for recommending {pick} came from the player liking {title}."
    if isinstance(e, ReviewRef):
        return sentence_case(f.line) + "."
    return f"Had the player not liked {f.cue}, {pick} would not have been recommended."


def premise(pack: Pack, listed: Sequence[Fact]) -> str:
    """What a sentence may rest on: the recommended game, every fact the model was given (so
    "the biggest reason" can be checked), and the graph paths the prompt offered as context."""
    pick = pack.pick_title
    lines = [f"The recommended game is {pick}."]
    shares = [f for f in listed if isinstance(f.evidence, AttributionRef)]
    if shares:
        top = shares[0].cue.rsplit(", ", 1)[0]
        lines.append(f"The biggest reason for recommending {pick} is that the player liked {top}.")
    lines += [statement(pick, f) for f in listed]
    lines += [f"{pick} {p}." for p in pack.paths]
    return "\n".join(lines)


def label(backend: Backend, premise_text: str, sentence: str, *, seed: int) -> str:
    """The judge's label, or "invalid" when its answer is not one of the labels."""
    raw = backend.complete(
        PROMPT.format(premise=premise_text, sentence=sentence), seed=seed, schema=SCHEMA
    )
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        return "invalid"
    value = doc.get("label") if isinstance(doc, dict) else None
    return value if isinstance(value, str) and value in LABELS else "invalid"


def labels(
    backend: Backend, pack: Pack, claims: Sequence[Claim], listed: Sequence[Fact], *, seed: int
) -> list[str]:
    """One label per claim, each read against all the facts."""
    text = premise(pack, listed)
    return [label(backend, text, c.text, seed=seed) for c in claims]


def shares(labels: Iterable[str]) -> dict[str, float | int | None]:
    """How often each label was given, with the count of sentences judged."""
    counts = Counter(labels)
    n = sum(counts.values())
    out: dict[str, float | int | None] = {"sentences": n}
    for key in (*LABELS, "invalid"):
        out[key] = counts[key] / n if n else None
    return out
