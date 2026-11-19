"""Natural-language queries for the API (FR-18, FR-23): the Python twin of web/src/lib/query.ts.

Clauses are separated by commas, semicolons, "and" or "with" (a title containing one stays whole):
"like X", "similar to X" or a bare exact title become anchors; any tag of the catalogue (and a few
synonyms) becomes a tag filter; "under $20", "free", "after 2012", "since 2012", "before 2010",
"until 2010", "2010 to 2014", "2010s" and a bare year set price and year. Everything else is
returned as unresolved.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

SYNONYMS = {
    "coop": "Co-op",
    "cooperative": "Co-op",
    "singleplayer": "Singleplayer",
    "solo": "Singleplayer",
    "multiplayer": "Multiplayer",
    "scifi": "Sci-fi",
    "sciencefiction": "Sci-fi",
    "roguelite": "Rogue-lite",
    "roguelike": "Rogue-like",
    "shooter": "Shooter",
    "fps": "FPS",
    "rpg": "RPG",
}
PRICE = re.compile(
    r"^(?:under|below|less than|cheaper than|max|up to|<)"
    r"\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:dollars|usd)?$"
)
AFTER = re.compile(r"^(after|since|from)\s+((?:19|20)\d\d)$")
BEFORE = re.compile(r"^(before|until|up to|through)\s+((?:19|20)\d\d)$")
RANGE = re.compile(r"^((?:19|20)\d\d)\s*(?:-|to|–|—)\s*((?:19|20)\d\d)$")
DECADE = re.compile(r"^((?:19|20)\d)0s$")
LIKE = re.compile(r"^(?:games?\s+)?(?:like|similar to)\s+(.+)$")
SPLIT = re.compile(r"(,|;|\band\b|\bwith\b)", re.IGNORECASE)


@dataclass
class Parsed:
    anchors: list[int] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    max_price: float | None = None
    year_min: int | None = None
    year_max: int | None = None
    unresolved: list[str] = field(default_factory=list)


def fold(text: str) -> str:
    """Lower case, letters and digits only: "Co-op" and "co op" both become "coop"."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return re.sub(r"[^a-z0-9]+", "", "".join(c for c in decomposed if not unicodedata.combining(c)))


def find_game(phrase: str, games: Sequence[dict[str, Any]]) -> int | None:
    """Exact title, then a title starting with the phrase, then containing it; most played wins."""
    want = fold(phrase)
    if len(want) < 2:
        return None
    best: tuple[int, int, int] | None = None  # (quality, plays, -index)
    for i, g in enumerate(games):
        t = fold(str(g["title"]))
        quality = (
            3
            if t == want
            else 2
            if t.startswith(want)
            else 1
            if len(want) >= 4 and want in t
            else 0
        )
        if quality:
            key = (quality, int(g.get("plays") or 0), -i)
            if best is None or key > best:
                best = key
    return -best[2] if best is not None else None


def _is_title(phrase: str, titles: set[str]) -> bool:
    c = phrase.strip().lower()
    m = LIKE.match(c)
    name = fold(m.group(1) if m else c)
    return len(name) > 1 and name in titles


def clauses(text: str, games: Sequence[dict[str, Any]]) -> list[str]:
    titles = {fold(str(g["title"])) for g in games}
    parts = SPLIT.split(text)
    out: list[str] = []
    i = 0
    while i < len(parts):
        for j in range(min(len(parts) - 1, i + 4), i, -2):
            joined = "".join(parts[i : j + 1])
            if _is_title(joined, titles):
                out.append(joined.strip())
                i = j + 2
                break
        else:
            if parts[i].strip():
                out.append(parts[i].strip())
            i += 2
    return out


def parse_query(text: str, games: Sequence[dict[str, Any]]) -> Parsed:
    vocabulary = {fold(t): t for g in games for t in (g.get("tags") or [])}
    out = Parsed()

    def anchor(i: int) -> None:
        if i not in out.anchors:
            out.anchors.append(i)

    for raw in clauses(text, games):
        c = re.sub(r"\s+", " ", raw.lower())
        if m := LIKE.match(c):
            i = find_game(m.group(1), games)
            if i is None:
                out.unresolved.append(raw)
            else:
                anchor(i)
        elif c in ("free", "free to play", "f2p"):
            out.max_price = 0.0
        elif m := PRICE.match(c):
            out.max_price = float(m.group(1))
        elif m := AFTER.match(c):
            out.year_min = int(m.group(2)) + (1 if m.group(1) == "after" else 0)
        elif m := BEFORE.match(c):
            out.year_max = int(m.group(2)) - (1 if m.group(1) == "before" else 0)
        elif m := RANGE.match(c):
            a, b = int(m.group(1)), int(m.group(2))
            out.year_min, out.year_max = min(a, b), max(a, b)
        elif m := DECADE.match(c):
            out.year_min = int(m.group(1) + "0")
            out.year_max = out.year_min + 9
        elif re.fullmatch(r"(?:19|20)\d\d", c):
            out.year_min = out.year_max = int(c)
        else:
            key = fold(c)
            tag = vocabulary.get(key)
            if tag is None and key in SYNONYMS and fold(SYNONYMS[key]) in vocabulary:
                tag = SYNONYMS[key]
            if tag is not None:
                if tag not in out.tags:
                    out.tags.append(tag)
                continue
            i = find_game(c, games)
            if i is not None and fold(str(games[i]["title"])) == fold(c):
                anchor(i)
            else:
                out.unresolved.append(raw)
    return out
