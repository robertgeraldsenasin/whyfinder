"""Grounded generation (FR-16; ADR-0009; docs/spec/06_RAG.md steps 4 and 6).

A small local model only voices facts the recommender already computed: the pick's top
attributions, its counterfactual set and review quotes retrieved for it, each listed with an ID
and shown as data rather than as a sentence the model could copy. The model writes one to three
sentences, each about one fact, and gives that fact's ID. Its output is held by the per-prompt
JSON schema: each sentence must match a pattern for its fact (the liked game's exact title, the
exact percentage if any, a player quote verbatim between curly quotes, and a full stop at the end,
so a length bound shows up as a short sentence rather than a cut one), which Ollama enforces while
decoding. Code attaches the evidence behind each ID.
`claims.check` then verifies every sentence against its evidence; on failure the model gets one
retry with the checker's reasons, then the template sentences take over (faithful by
construction). Generations are cached under hash(model, digest, prompt, schema, seed): CI replays
the cache and fails on a miss, so it costs nothing and gives the same result every run.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from whyfinder.rag.claims import (
    MAX_CLAIMS,
    MAX_WORDS,
    TOP,
    AttributionRef,
    Claim,
    CounterfactualRef,
    Evidence,
    ReviewRef,
    SchemaError,
    Source,
    check,
)


@dataclass(frozen=True)
class Pack:
    """The facts for one pick, in the order the prompt lists them."""

    pick_title: str
    liked: tuple[tuple[str, str], ...]  # every liked game, (game_id, title), in the player's order
    attributions: tuple[tuple[str, str, float], ...]  # (game_id, title, share), largest first
    removed: tuple[tuple[str, str], ...]  # the counterfactual set, (game_id, title)
    paths: tuple[str, ...]  # "shares the tag Comedy with Portal 2"
    kept_for_variety: bool
    quotes: tuple[tuple[str, str, str], ...]  # (chunk_id, aspect, text)


RULES = (
    "Write in English. Tell a player why the game below was recommended to them, in one to "
    "{claims} short sentences and {words} words in all. Each sentence uses exactly one fact from "
    "the list and gives its ID. Say the fact in your own words, the way you would tell the "
    "player; do not copy the fact as listed. A sentence about a liked game names it exactly as "
    "written; if it gives a number, it is the percentage listed. A sentence about a player quote "
    "copies the quote word for word between \u201c and \u201d. Do not mention any game that is "
    "not in the facts. End every sentence with a full stop."
)

BLIND = (
    "Write in English. Tell a player why the game below was recommended to them, in one to "
    "{claims} short sentences and {words} words in all. You know which games the player liked, "
    "not how much each one counted. Each sentence is about one liked game, names it exactly as "
    "written and gives its ID. Do not mention any game that is not in the facts. End every "
    "sentence with a full stop."
)

FREE = '[^%"\\\\\u201c\u201d]'  # anything but %, straight or curly double quotes, backslash
END = "[.!]"  # every sentence ends on its own; a bound that bites leaves a short sentence
META = set("\\^$.|?*+()[]{}/")


def literal(text: str) -> str:
    """`text` as a regex that matches only itself (the subset llama.cpp grammars accept)."""
    return "".join("\\" + c if c in META else c for c in text)


def span(most: int) -> str:
    """Up to `most` characters of free text."""
    return f"{FREE}{{0,{most}}}"


@dataclass(frozen=True)
class Fact:
    id: str
    line: str  # the fact as a plain sentence: what the demo shows and the judge reads
    evidence: Evidence
    pattern: str  # what a sentence about this fact must look like
    cue: str  # the fact as the prompt lists it, as data rather than a sentence to copy


def about(title: str) -> str:
    return f"^{span(50)}{literal(title)}{span(80)}{END}$"


def facts(pack: Pack, *, with_attributions: bool = True) -> list[Fact]:
    """The citable facts, with IDs: A for attributions, C for the counterfactual, Q for quotes;
    without attributions (the research ablation) only L for the liked games, in the player's
    order, since the attribution order would give the answer away. Quotes containing straight
    double quotes or backslashes are left out: they cannot be pinned inside a JSON string."""
    if not with_attributions:
        return [
            Fact(f"L{n}", title, AttributionRef(gid, 0.0), about(title), f"(liked) {title}")
            for n, (gid, title) in enumerate(pack.liked, start=1)
        ]
    out: list[Fact] = []
    positive = [a for a in pack.attributions[:TOP] if a[2] > 0]
    for n, (gid, title, share) in enumerate(positive, start=1):
        pct = round(share * 100)
        line = f"{title} counted for {pct}% of the score"
        lead = f"({span(50)}|{span(30)}{pct}%{span(40)})"  # the share may come first
        pattern = f"^{lead}{literal(title)}{span(60)}({pct}%{span(50)})?{END}$"
        cue = f"(liked) {title}: {pct}% of the score"
        out.append(Fact(f"A{n}", line, AttributionRef(gid, share), pattern, cue))
    if pack.removed:
        names = " and ".join(t for _, t in pack.removed)
        line = f"without {names} in the list, {pack.pick_title} would drop out of the picks"
        joined = f"{FREE}{{1,25}}".join(literal(t) for _, t in pack.removed)
        pattern = f"^{span(50)}{joined}{span(80)}{END}$"
        cue = f"(remove these and the pick drops out) {names}"
        ids = tuple(g for g, _ in pack.removed)
        out.append(Fact("C1", line, CounterfactualRef(ids), pattern, cue))
    usable = [q for q in pack.quotes if '"' not in q[2] and "\\" not in q[2]]
    for n, (cid, aspect, text) in enumerate(usable, start=1):
        line = f"a player of {pack.pick_title}, on {aspect}: \u201c{text}\u201d"
        pattern = f"^{span(60)}\u201c{literal(text)}\u201d({span(20)}{END})?$"
        cue = f"(a player of {pack.pick_title}, on {aspect}) \u201c{text}\u201d"
        out.append(Fact(f"Q{n}", line, ReviewRef(cid, text), pattern, cue))
    return out


def schema(listed: Sequence[Fact]) -> dict[str, Any]:
    """The output the model is held to: one to three sentences, each naming one fact by ID and
    matching that fact's pattern."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["claims"],
        "properties": {
            "claims": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_CLAIMS,
                "items": {
                    "anyOf": [
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["fact", "text"],
                            "properties": {
                                "fact": {"enum": [f.id]},
                                "text": {"type": "string", "pattern": f.pattern},
                            },
                        }
                        for f in listed
                    ]
                },
            }
        },
    }


def prompt(pack: Pack, *, with_attributions: bool = True, feedback: Sequence[str] = ()) -> str:
    """The prompt for a pack; `with_attributions=False` is the research ablation (06_RAG)."""
    rules = (RULES if with_attributions else BLIND).format(claims=MAX_CLAIMS, words=MAX_WORDS)
    listed = "\n".join(f"{f.id} {f.cue}" for f in facts(pack, with_attributions=with_attributions))
    text = f"{rules}\n\nRecommended game: {pack.pick_title}\nFacts:\n{listed}\n"
    if with_attributions and pack.paths:
        also = "; ".join(f"{pack.pick_title} {p}" for p in pack.paths)
        text += f"Also true, may be mentioned but has no ID: {also}.\n"
    text += '\nAnswer with JSON only: {"claims": [{"fact": "...", "text": "..."}]}\n'
    if feedback:
        text += "\nYour last answer was rejected:\n" + "\n".join(f"- {r}" for r in feedback)
        text += "\nAnswer again, fixing every point.\n"
    return text


def read(raw: str, listed: Sequence[Fact]) -> list[Claim]:
    """Claims from the model's answer: each sentence with the evidence behind its fact's ID."""
    by_id = {f.id: f for f in listed}
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"not JSON: {exc.msg}") from exc
    items = doc.get("claims") if isinstance(doc, dict) else None
    if not isinstance(items, list) or set(doc) != {"claims"}:
        raise SchemaError('the answer must be {"claims": [...]}')
    if len(items) > MAX_CLAIMS:
        raise SchemaError(f"at most {MAX_CLAIMS} sentences")
    out: list[Claim] = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"fact", "text"}:
            raise SchemaError("each sentence needs exactly fact and text")
        fact, text = item["fact"], item["text"]
        if not isinstance(text, str) or not text.strip():
            raise SchemaError("a sentence must be a non-empty string")
        if not isinstance(fact, str) or fact not in by_id:
            raise SchemaError(f"fact must be an ID from the list, got {fact!r}")
        out.append(Claim(text=text, evidence=(by_id[fact].evidence,)))
    return out


class Backend(Protocol):
    model: str

    @property
    def digest(self) -> str: ...

    def complete(self, prompt: str, *, seed: int, schema: dict[str, Any]) -> str: ...


class CacheMissError(RuntimeError):
    """A prompt the cache has no answer for, in replay-only mode."""


class LlmUnavailableError(RuntimeError):
    """The model server could not be reached or answered with an error."""


@dataclass
class Ollama:
    """A local model through Ollama's HTTP API, constrained to the claim schema."""

    model: str
    url: str = "http://127.0.0.1:11434"
    timeout: float = 300.0
    _digest: str | None = None

    def _post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode()
        method = "GET" if body is None else "POST"
        if not self.url.startswith(("http://", "https://")):
            raise LlmUnavailableError(f"not an HTTP URL: {self.url}")
        headers = {"content-type": "application/json"}
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=headers)  # noqa: S310
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:  # noqa: S310
                out: dict[str, Any] = json.loads(response.read())
                return out
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LlmUnavailableError(f"{self.url}{path}: {exc}") from exc

    @property
    def digest(self) -> str:
        if self._digest is None:
            tags = self._post("/api/tags").get("models", [])
            match = [m for m in tags if m.get("name") in (self.model, f"{self.model}:latest")]
            if not match:
                raise LlmUnavailableError(f"model {self.model} is not pulled on {self.url}")
            self._digest = str(match[0]["digest"])
        return self._digest

    def complete(self, prompt: str, *, seed: int, schema: dict[str, Any]) -> str:
        body = {
            "model": self.model,
            "prompt": prompt,
            "format": schema,
            "stream": False,
            "options": {"temperature": 0, "seed": seed, "num_predict": 400},
        }
        return str(self._post("/api/generate", body)["response"])


@dataclass
class Cache:
    """Generations keyed by hash(model, digest, prompt, seed), one JSON line each."""

    path: Path
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Cache:
        entries: dict[str, dict[str, Any]] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    entries[row["key"]] = row
        return cls(path, entries)

    @staticmethod
    def key(model: str, digest: str, prompt: str, schema: dict[str, Any], seed: int) -> str:
        raw = json.dumps([model, digest, prompt, schema, seed], ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps(self.entries[k], ensure_ascii=False, sort_keys=True)
            for k in sorted(self.entries)
        ]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


@dataclass
class Cached:
    """A backend behind the cache. Without an inner backend it only replays (CI)."""

    cache: Cache
    model: str
    known_digest: str
    inner: Backend | None = None

    @property
    def digest(self) -> str:
        return self.known_digest

    def complete(self, prompt: str, *, seed: int, schema: dict[str, Any]) -> str:
        key = Cache.key(self.model, self.known_digest, prompt, schema, seed)
        hit = self.cache.entries.get(key)
        if hit is not None:
            return str(hit["response"])
        if self.inner is None:
            raise CacheMissError(
                f"no cached generation for this prompt ({key[:12]}); refresh the cache with the "
                "llm workflow or run with a local model"
            )
        response = self.inner.complete(prompt, seed=seed, schema=schema)
        self.cache.entries[key] = {
            "key": key,
            "model": self.model,
            "digest": self.known_digest,
            "seed": seed,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "response": response,
        }
        return response


@dataclass(frozen=True)
class Attempt:
    raw: str
    claims: list[Claim]
    reasons: list[str]


@dataclass(frozen=True)
class Outcome:
    claims: list[Claim]
    used: Literal["model", "model-retry", "template"]
    attempts: list[Attempt]

    @property
    def fallback_used(self) -> bool:
        return self.used == "template"


def attempt(raw: str, listed: Sequence[Fact], source: Source) -> Attempt:
    try:
        claims = read(raw, listed)
    except SchemaError as exc:
        return Attempt(raw, [], [f"the output does not follow the claim schema: {exc}"])
    if not claims:
        return Attempt(raw, [], ["no claims"])
    return Attempt(raw, claims, check(claims, source))


def ask(
    backend: Backend,
    pack: Pack,
    source: Source,
    *,
    seed: int,
    with_attributions: bool = True,
    feedback: Sequence[str] = (),
) -> Attempt:
    listed = facts(pack, with_attributions=with_attributions)
    text = prompt(pack, with_attributions=with_attributions, feedback=feedback)
    return attempt(backend.complete(text, seed=seed, schema=schema(listed)), listed, source)


def explain(
    pack: Pack,
    source: Source,
    backend: Backend,
    template: Callable[[], list[Claim]],
    *,
    seed: int,
) -> Outcome:
    """Generate, check, retry once with the checker's reasons, then fall back to the template."""
    first = ask(backend, pack, source, seed=seed)
    if not first.reasons:
        return Outcome(first.claims, "model", [first])
    second = ask(backend, pack, source, seed=seed, feedback=first.reasons)
    if not second.reasons:
        return Outcome(second.claims, "model-retry", [first, second])
    return Outcome(template(), "template", [first, second])


def template(pack: Pack) -> list[Claim]:
    """Sentences built straight from the facts: the top attribution, the second when it carries at
    least 10%, then quotes, within the claim and word limits."""
    claims: list[Claim] = []
    positive = [a for a in pack.attributions if a[2] > 0]
    for n, (gid, title, share) in enumerate(positive[:2]):
        if n == 1 and share < 0.1:
            break
        pct = f"{round(share * 100)}%"
        text = (
            f"{title} is the biggest driver of this pick ({pct})."
            if n == 0
            else f"{title} adds {pct}."
        )
        claims.append(Claim(text, (AttributionRef(gid, share),)))
    for cid, aspect, quote in pack.quotes:
        claims.append(
            Claim(
                f'Players of {pack.pick_title} mention {aspect}: "{quote}"',
                (ReviewRef(cid, quote),),
            )
        )
    out: list[Claim] = []
    words = 0
    for claim in claims:
        n = len(claim.text.split())
        if len(out) == MAX_CLAIMS or words + n > MAX_WORDS:
            break
        out.append(claim)
        words += n
    return out
