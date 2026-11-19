"""Grounded generation (FR-16; ADR-0009; docs/spec/06_RAG.md steps 4 and 6).

A small local model only voices facts the recommender already computed: the pick's top
attributions, its counterfactual set, graph paths, the variety flag and review quotes retrieved for
it. It answers in the claim schema at temperature 0; `claims.check` verifies every claim; on failure
the model gets one retry with the checker's reasons, then the template sentences take over (faithful
by construction). Generations are cached under hash(model, digest, prompt, seed): CI replays the
cache and fails on a miss, so it costs nothing and gives the same result every run.
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
    SCHEMA,
    TOP,
    AttributionRef,
    Claim,
    ReviewRef,
    SchemaError,
    Source,
    check,
    parse,
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


INSTRUCTIONS = (
    "You explain one game recommendation to a player in at most {claims} short claims and "
    "{words} words in all. Use only the facts below. Every claim must cite its evidence:\n"
    '- {{"type": "attribution", "game_id": ..., "share": ...}} for a liked game that drove the '
    "pick; name that game in the sentence; if you give a percentage, it is the share times 100;\n"
    '- {{"type": "review", "chunk_id": ..., "quote": ...}} for a player quote; copy the quote '
    "exactly and put it in the sentence in double quotes, at most 25 words;\n"
    '- {{"type": "counterfactual", "removed_game_ids": [...]}} only for the exact set listed.\n'
    "Name no game that is not in the facts. Answer with JSON only: "
    '{{"claims": [{{"text": ..., "evidence": [...]}}]}}.'
)

ABLATION = (
    "You explain one game recommendation to a player in at most {claims} short claims and "
    "{words} words in all. You are told which games the player liked, not how much each one "
    'counted. Every claim must cite one liked game as {{"type": "attribution", "game_id": ..., '
    '"share": 0}}; name that game in the sentence. Name no game that is not in the facts. '
    'Answer with JSON only: {{"claims": [{{"text": ..., "evidence": [...]}}]}}.'
)


def prompt(pack: Pack, *, with_attributions: bool = True, feedback: Sequence[str] = ()) -> str:
    """The prompt for a pack; `with_attributions=False` is the research ablation (06_RAG)."""
    facts: dict[str, Any] = {"recommended": pack.pick_title}
    if with_attributions:
        facts["why"] = [
            {"game_id": gid, "liked_game": title, "share": round(share, 3)}
            for gid, title, share in pack.attributions[:TOP]
        ]
        if pack.removed:
            facts["counterfactual"] = {
                "removed_game_ids": [gid for gid, _ in pack.removed],
                "means": "without all of "
                + ", ".join(t for _, t in pack.removed)
                + " in the list, the pick drops out",
            }
        if pack.paths:
            facts["related_by"] = list(pack.paths)
        if pack.kept_for_variety:
            facts["kept_for_variety"] = True
        if pack.quotes:
            facts["player_quotes"] = [
                {"chunk_id": cid, "about": aspect, "quote": text}
                for cid, aspect, text in pack.quotes
            ]
        head = INSTRUCTIONS.format(claims=MAX_CLAIMS, words=MAX_WORDS)
    else:
        # The player's own order: the attribution order would leak the answer.
        facts["liked_games"] = [{"game_id": gid, "title": title} for gid, title in pack.liked]
        head = ABLATION.format(claims=MAX_CLAIMS, words=MAX_WORDS)
    text = f"{head}\n\nFacts: {json.dumps(facts, ensure_ascii=False)}\n"
    if feedback:
        text += "\nYour last answer was rejected:\n" + "\n".join(f"- {r}" for r in feedback)
        text += "\nAnswer again, fixing every point.\n"
    return text


class Backend(Protocol):
    model: str

    @property
    def digest(self) -> str: ...

    def complete(self, prompt: str, *, seed: int) -> str: ...


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

    def complete(self, prompt: str, *, seed: int) -> str:
        body = {
            "model": self.model,
            "prompt": prompt,
            "format": SCHEMA,
            "stream": False,
            "options": {"temperature": 0, "seed": seed, "num_predict": 512},
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
    def key(model: str, digest: str, prompt: str, seed: int) -> str:
        raw = json.dumps([model, digest, prompt, seed], ensure_ascii=False)
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

    def complete(self, prompt: str, *, seed: int) -> str:
        key = Cache.key(self.model, self.known_digest, prompt, seed)
        hit = self.cache.entries.get(key)
        if hit is not None:
            return str(hit["response"])
        if self.inner is None:
            raise CacheMissError(
                f"no cached generation for this prompt ({key[:12]}); refresh the cache with the "
                "llm workflow or run with a local model"
            )
        response = self.inner.complete(prompt, seed=seed)
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


def attempt(raw: str, source: Source) -> Attempt:
    try:
        claims = parse(raw)
    except SchemaError as exc:
        return Attempt(raw, [], [f"the output does not follow the claim schema: {exc}"])
    if not claims:
        return Attempt(raw, [], ["no claims"])
    return Attempt(raw, claims, check(claims, source))


def explain(
    pack: Pack,
    source: Source,
    backend: Backend,
    template: Callable[[], list[Claim]],
    *,
    seed: int,
) -> Outcome:
    """Generate, check, retry once with the checker's reasons, then fall back to the template."""
    first = attempt(backend.complete(prompt(pack), seed=seed), source)
    if not first.reasons:
        return Outcome(first.claims, "model", [first])
    second = attempt(backend.complete(prompt(pack, feedback=first.reasons), seed=seed), source)
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
