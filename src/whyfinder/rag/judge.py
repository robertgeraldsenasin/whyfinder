"""Entailment of generated sentences, labelled by a second local model (06_RAG, "Evaluation").

The checker proves what it can parse in a sentence: titles, shares, quotes, the counterfactual
set. Whatever a model writes around them (why a share matters, what two games have in common)
passes unread. Here a judge model reads each sentence against the facts it cites, plus the graph
paths the prompt gave as context, and labels it the way natural-language inference does:

- **entailed**: everything the sentence states follows from those facts; rewording is fine;
- **neutral**: it adds something the facts neither give nor contradict (an opinion of the game,
  a reason that is not there);
- **contradicted**: some part conflicts with them.

The template sentences go through the same judge as a control. They are entailed by construction,
so whatever share the judge labels otherwise is its own error, and the model's numbers should be
read next to it. A judge grading its own sentences is flagged. Judgments are cached under the same
key as generations and replayed in CI.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any, Final

from whyfinder.rag.claims import Claim
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
    "You check a sentence written from facts.\n\n"
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


def premise(pack: Pack, claim: Claim, listed: Sequence[Fact]) -> str:
    """What the sentence may rest on: the recommended game, the facts it cites, and the graph
    paths the prompt offered as context."""
    lines = [f"The recommended game is {pack.pick_title}."]
    lines += [sentence_case(f.line) + "." for f in listed if f.evidence in claim.evidence]
    lines += [f"{pack.pick_title} {p}." for p in pack.paths]
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
    """One label per claim, each read against the facts it cites."""
    return [label(backend, premise(pack, c, listed), c.text, seed=seed) for c in claims]


def shares(labels: Iterable[str]) -> dict[str, float | int | None]:
    """How often each label was given, with the count of sentences judged."""
    counts = Counter(labels)
    n = sum(counts.values())
    out: dict[str, float | int | None] = {"sentences": n}
    for key in (*LABELS, "invalid"):
        out[key] = counts[key] / n if n else None
    return out
