"""Claims and the claim checker (FR-16, FR-17; docs/spec/06_RAG.md steps 4-5).

A claim is a sentence with its evidence: an attribution (a liked game and its share of the
score), a review span (a chunk and a verbatim quote), or the counterfactual set. `parse` reads a
model's JSON against `SCHEMA` (also committed as docs/spec/claim.schema.json); `check` applies the
deterministic rules, so a sentence the model got wrong never reaches a user.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

MAX_CLAIMS = 3
MAX_WORDS = 60
MAX_QUOTE_WORDS = 25
TOP = 5
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


@dataclass(frozen=True)
class AttributionRef:
    game_id: str
    share: float


@dataclass(frozen=True)
class ReviewRef:
    chunk_id: str
    quote: str


@dataclass(frozen=True)
class CounterfactualRef:
    removed_game_ids: tuple[str, ...]


Evidence = AttributionRef | ReviewRef | CounterfactualRef


@dataclass(frozen=True)
class Claim:
    text: str
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class Source:
    """What a pick's claims may rest on: the facts E1-E2 computed and the chunks retrieved."""

    pick_title: str
    attributions: Mapping[str, tuple[str, float]]  # game_id → (title, share), largest first
    chunks: Mapping[str, str]  # chunk_id → text (the pick's retrieved chunks)
    removed: frozenset[str] = frozenset()  # the counterfactual set
    catalogue: tuple[str, ...] = ()
    extra_allowed: frozenset[str] = field(default_factory=frozenset)


SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://github.com/robertgeraldsenasin/whyfinder/docs/spec/claim.schema.json",
    "title": "Claims about one recommendation",
    "type": "object",
    "additionalProperties": False,
    "required": ["claims"],
    "properties": {
        "claims": {
            "type": "array",
            "maxItems": MAX_CLAIMS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "evidence"],
                "properties": {
                    "text": {"type": "string", "minLength": 1},
                    "evidence": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "oneOf": [
                                {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["type", "game_id", "share"],
                                    "properties": {
                                        "type": {"const": "attribution"},
                                        "game_id": {"type": "string"},
                                        "share": {"type": "number"},
                                    },
                                },
                                {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["type", "chunk_id", "quote"],
                                    "properties": {
                                        "type": {"const": "review"},
                                        "chunk_id": {"type": "string"},
                                        "quote": {"type": "string", "minLength": 1},
                                    },
                                },
                                {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["type", "removed_game_ids"],
                                    "properties": {
                                        "type": {"const": "counterfactual"},
                                        "removed_game_ids": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "minItems": 1,
                                        },
                                    },
                                },
                            ]
                        },
                    },
                },
            },
        }
    },
}


class SchemaError(ValueError):
    """The model's output is not a claims document."""


def _evidence(raw: object) -> Evidence:
    if not isinstance(raw, dict):
        raise SchemaError("evidence must be an object")
    kind = raw.get("type")
    keys = set(raw)
    if kind == "attribution" and keys == {"type", "game_id", "share"}:
        share = raw["share"]
        if not isinstance(raw["game_id"], str) or not isinstance(share, int | float):
            raise SchemaError("attribution evidence needs a string game_id and a numeric share")
        if isinstance(share, bool):
            raise SchemaError("share must be a number")
        return AttributionRef(raw["game_id"], float(share))
    if kind == "review" and keys == {"type", "chunk_id", "quote"}:
        if not isinstance(raw["chunk_id"], str) or not isinstance(raw["quote"], str):
            raise SchemaError("review evidence needs a string chunk_id and quote")
        if not raw["quote"]:
            raise SchemaError("a quote cannot be empty")
        return ReviewRef(raw["chunk_id"], raw["quote"])
    if kind == "counterfactual" and keys == {"type", "removed_game_ids"}:
        ids = raw["removed_game_ids"]
        if not isinstance(ids, list) or not ids or not all(isinstance(g, str) for g in ids):
            raise SchemaError("counterfactual evidence needs a non-empty list of game IDs")
        return CounterfactualRef(tuple(ids))
    raise SchemaError(f"unknown or malformed evidence: {sorted(keys)}")


def parse(raw: str) -> list[Claim]:
    """Claims from a model's JSON output, validated against SCHEMA (raises SchemaError)."""
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"not JSON: {exc.msg}") from exc
    if not isinstance(doc, dict) or set(doc) != {"claims"} or not isinstance(doc["claims"], list):
        raise SchemaError('the output must be {"claims": [...]}')
    if len(doc["claims"]) > MAX_CLAIMS:
        raise SchemaError(f"at most {MAX_CLAIMS} claims")
    out = []
    for item in doc["claims"]:
        if not isinstance(item, dict) or set(item) != {"text", "evidence"}:
            raise SchemaError("each claim needs exactly text and evidence")
        text, evidence = item["text"], item["evidence"]
        if not isinstance(text, str) or not text.strip():
            raise SchemaError("a claim's text must be a non-empty string")
        if not isinstance(evidence, list) or not evidence:
            raise SchemaError("each claim needs at least one piece of evidence")
        out.append(Claim(text=text, evidence=tuple(_evidence(e) for e in evidence)))
    return out


def dump(claims: Iterable[Claim]) -> dict[str, object]:
    """The JSON document for claims (the inverse of `parse`)."""

    def one(e: Evidence) -> dict[str, object]:
        if isinstance(e, AttributionRef):
            return {"type": "attribution", "game_id": e.game_id, "share": e.share}
        if isinstance(e, ReviewRef):
            return {"type": "review", "chunk_id": e.chunk_id, "quote": e.quote}
        return {"type": "counterfactual", "removed_game_ids": list(e.removed_game_ids)}

    return {"claims": [{"text": c.text, "evidence": [one(e) for e in c.evidence]} for c in claims]}


def is_verbatim(quote: str, text: str) -> bool:
    """A quote is a span of the chunk (whitespace normalised), 1 to 25 words long."""
    words = quote.split()
    return 0 < len(words) <= MAX_QUOTE_WORDS and " ".join(words) in " ".join(text.split())


MARKS = ("\u00ae", "\u2122", "\u00a9")  # ® ™ ©, which players rarely type


def bare(text: str) -> str:
    """`text` without trademark signs, whitespace normalised: how a title is usually written."""
    for mark in MARKS:
        text = text.replace(mark, "")
    return " ".join(text.split())


def names(text: str, title: str) -> bool:
    """The sentence names the title, with or without its trademark signs."""
    return title in text or bare(title) in bare(text)


def unlisted_games(
    text: str, quotes: Iterable[str], catalogue: Iterable[str], allowed: set[str]
) -> list[str]:
    """Catalogue titles a sentence names, outside its quotes, that are not allowed, with or without
    their trademark signs. Allowed titles are blanked first, longest first, so "Portal 2" never
    reads as "Portal"."""
    rest = text
    for quote in quotes:
        rest = rest.replace(quote, " ")
    rest = bare(rest)
    for title in sorted({bare(a) for a in allowed}, key=len, reverse=True):
        rest = re.sub(rf"(?<!\w){re.escape(title)}(?!\w)", " ", rest)
    return [
        title
        for title in catalogue
        if title not in allowed
        and len(bare(title)) > 3
        and re.search(rf"(?<!\w){re.escape(bare(title))}(?!\w)", rest)
    ]


def check(claims: list[Claim], source: Source) -> list[str]:
    """Every reason the claims fail FR-17; empty when they all pass.

    - attribution: the game is among the top five, the share is the computed one, the sentence names
      the game, and any percentage in it is within one point of a cited share;
    - review: the chunk was retrieved for this pick and the quote is a verbatim span of it (≤ 25
      words) that the sentence carries;
    - counterfactual: the set is exactly the computed one;
    - every claim: at least one piece of evidence; no game named outside the pick, the history and
      the quotes; at most three claims and sixty words in all.
    """
    reasons: list[str] = []
    if len(claims) > MAX_CLAIMS:
        reasons.append(f"more than {MAX_CLAIMS} claims")
    words = sum(len(c.text.split()) for c in claims)
    if words > MAX_WORDS:
        reasons.append(f"{words} words; the limit is {MAX_WORDS}")
    top = dict(list(source.attributions.items())[:TOP])
    allowed = {source.pick_title, *(t for t, _ in source.attributions.values())}
    allowed |= set(source.extra_allowed)
    for claim in claims:
        if not claim.evidence:
            reasons.append(f"no evidence for: {claim.text}")
            continue
        quotes = [e.quote for e in claim.evidence if isinstance(e, ReviewRef)]
        reasons += [
            f"names a game outside the pick and the history: {g}"
            for g in unlisted_games(claim.text, quotes, source.catalogue, allowed)
        ]
        cited: list[float] = []
        for e in claim.evidence:
            if isinstance(e, AttributionRef):
                fact = top.get(e.game_id)
                if fact is None:
                    reasons.append(f"cites a game that is not among the top {TOP}: {e.game_id}")
                    continue
                title, share = fact
                if abs(share - e.share) > 0.005:
                    reasons.append(f"wrong share for {title}: {e.share:.3f}, not {share:.3f}")
                elif not names(claim.text, title):
                    reasons.append(f"cites {title} without naming it")
                cited.append(share)
            elif isinstance(e, ReviewRef):
                text = source.chunks.get(e.chunk_id)
                if text is None:
                    reasons.append(
                        f"cites a review chunk not retrieved for this pick: {e.chunk_id}"
                    )
                elif not is_verbatim(e.quote, text):
                    reasons.append(f"the quote is not a verbatim span of {e.chunk_id}")
                elif e.quote not in claim.text:
                    reasons.append(f"the sentence does not carry its quote from {e.chunk_id}")
            elif frozenset(e.removed_game_ids) != source.removed:
                reasons.append("the counterfactual set is not the computed one")
        outside = claim.text
        for quote in quotes:
            outside = outside.replace(quote, " ")
        for match in PERCENT.finditer(outside):
            stated = float(match.group(1)) / 100
            if not any(abs(stated - c) <= 0.01 + 1e-9 for c in cited):
                reasons.append(f"{match.group(0)} matches no cited share")
    return reasons
