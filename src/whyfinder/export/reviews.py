"""Review evidence for the demo: what players say, and what two communities share.

For each game in the demo slice, from Steam reviews written before T1 (the training period):

- **Terms players use** (`terms`): words that are distinctive for this game's reviews compared with
  all slice reviews, by the log-odds ratio with an informative Dirichlet prior (Monroe, Colaresi &
  Quinn, 2008), counted once per review. The demo intersects two games' lists to show what both
  communities talk about.
- **Quotes** (`quotes`): up to `quotes_per_game` single sentences of at most 25 words (NFR-07), each
  from a different player, chosen for positive wording, play time, and how many other slice games
  the player also reviewed (`also`, slice indices), so the demo can show "players who also played
  your game say…".

No usernames or user IDs are exported. Selection is deterministic (ties by review ID).
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

MAX_WORDS = 25
MIN_WORDS = 6
TOKEN = re.compile(r"[a-z][a-z'-]{2,}")
WORD = re.compile(r"[A-Za-z']+")
BBCODE = re.compile(r"\[/?[a-z0-9*]+(?:=[^\]]*)?\]", re.I)
URL = re.compile(r"https?://\S+|www\.\S+", re.I)
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


STOPWORDS = _words(
    """
    a about above after again against all almost also although always am an and any are aren't
    around as at be because been before being below between both but by can can't cannot could
    did didn't do does doesn't doing don't down during each even ever every few for from further
    get gets getting got had has have having he her here hers him his how however i i'd i'll i'm
    i've if in into is isn't it it's its itself just let's lot lots me more most much must my
    myself no nor not now of off on once one only or other our out over own quite rather really
    same she should so some still such than that that's the their them then there there's these
    they they're thing things this those though through to too under until up us very was wasn't
    way we well were what when where which while who whom why will with without won't would you
    you'll you're your yours yet
    """
)
#: Words every game's reviews share; never "distinctive".
GENERIC = _words(
    """
    game games play played playing player players steam hours hour time times buy bought buying
    worth money price recommend recommended review reviews good great best better bad fun like
    love loved enjoy enjoyed amazing awesome nice pretty first new make makes made want think
    know see say going go goes come back need lot people friend friends overall definitely
    actually still get sale early access update updates version developer developers dev devs
    gameplay install installed uninstall download downloaded
    """
)
POSITIVE = _words(
    """
    addictive amazing atmospheric awesome beautiful beautifully best blast brilliant captivating
    charming clever compelling creative delight delightful engaging enjoy enjoyable enjoyed epic
    excellent exceptional fantastic favorite favourite fun genius gorgeous great hooked
    immersive incredible incredibly love loved lovely masterpiece memorable outstanding perfect
    phenomenal polished recommend relaxing rewarding satisfying solid stunning superb wonderful
    worth
    """
)
NEGATIVE = _words(
    """
    annoying avoid awful bad boring broken buggy crash crashes crashing disappointed
    disappointing garbage hate horrible laggy mediocre meh refund refunded terrible trash
    unplayable useless waste worse worst ruined ruin ruins dead died dying sadly unfortunately
    hackers hacker hacking cheaters cheater cheating scam overpriced greedy cons flawed
    frustrating grindy repetitive shame absurd lag uninstall uninstalled problem problems
    """
)
NEGATIONS = frozenset(
    {"not", "no", "never", "don't", "doesn't", "didn't", "isn't", "wasn't", "can't"}
)
#: Stems that disqualify a sentence for public display (profanity and slurs).
BLOCKED_STEMS = (
    "fuck",
    "shit",
    "cunt",
    "nigg",
    "fag",
    "retard",
    "whore",
    "slut",
    "rape",
    "bitch",
    "drug",
    "used to",
    "that's it",
    "~",
)
BOILERPLATE = (
    "early access review",
    "product received for free",
    "rating:",
    "pros:",
    "cons:",
    "10/10",
)


@dataclass(frozen=True)
class Quote:
    text: str
    hours: float
    year: int | None
    also: list[int]
    score: float
    review_id: int


def clean_text(text: str) -> str:
    """Strip BBCode and URLs, collapse whitespace."""
    text = BBCODE.sub(" ", text)
    text = URL.sub(" ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def polarity(words: Sequence[str]) -> tuple[int, int]:
    """(positive, negative) word counts; a positive word after a negation counts as negative."""
    pos = neg = 0
    for k, w in enumerate(words):
        negated = k > 0 and words[k - 1] in NEGATIONS
        if w in POSITIVE:
            if negated:
                neg += 1
            else:
                pos += 1
        elif w in NEGATIVE and not negated:
            neg += 1
    return pos, neg


def displayable(sentence: str) -> bool:
    """English-looking prose without profanity, boilerplate, shouting or ASCII art."""
    low = sentence.lower()
    if any(stem in low for stem in BLOCKED_STEMS) or any(b in low for b in BOILERPLATE):
        return False
    letters = [c for c in sentence if c.isalpha()]
    if len(letters) < 0.7 * len(sentence.replace(" ", "")) or not letters:
        return False
    if sum(c.isupper() for c in letters) > 0.4 * len(letters):
        return False
    if any(ord(c) > 0x024F and not 0x2000 <= ord(c) <= 0x206F for c in sentence):
        return (
            False  # non-Latin scripts, symbols, emoji, box drawing (keeps curly quotes and dashes)
        )
    words = WORD.findall(low)
    return sum(w in STOPWORDS for w in words) >= 2


#: Lead-ins that make a sentence read as a fragment when quoted alone.
FRAGMENT_START = frozenset(
    {"and", "but", "or", "so", "because", "is", "was", "which", "then", "also"}
)
LEAD_IN = re.compile(
    r"^(?:in conclusion|conclusion|verdict|tl;?dr|summary|recommendation)\s*[:,-]\s*", re.I
)
PUNCT_RUN = re.compile(r"[!?.]{3,}|[!?]{2,}")


def tidy(sentence: str) -> str:
    """Light copy-editing that keeps the reviewer's words: lead-ins, stray spaces, doubled marks."""
    sentence = LEAD_IN.sub("", sentence.strip(" -*•\"'"))
    sentence = re.sub(r"\s+([,.!?;:])", r"\1", sentence)
    sentence = re.sub(r"[,;:]+([.!?])$", r"\1", sentence)
    return re.sub(r"!+$", "!", sentence)


def best_sentence(text: str, terms: frozenset[str]) -> tuple[str, float] | None:
    """The most quotable sentence (6–25 words, positive, no negative words) and its score."""
    best: tuple[str, float] | None = None
    for raw in SENTENCE.split(clean_text(text)):
        well_formed = raw[:1].isupper() and raw.rstrip().endswith((".", "!", "?"))
        sentence = tidy(raw)
        words = sentence.split()
        if not words or words[0].lower().strip(",") in FRAGMENT_START or PUNCT_RUN.search(sentence):
            continue
        if not MIN_WORDS <= len(words) <= MAX_WORDS or not displayable(sentence):
            continue
        toks = tokens(sentence)
        pos, neg = polarity(toks)
        if pos == 0 or neg > 0:
            continue
        score = pos + 0.5 * sum(t in terms for t in set(toks)) + 0.5 * well_formed
        if not sentence.endswith((".", "!", "?")):
            sentence += "."
        if best is None or score > best[1]:
            best = (sentence[0].upper() + sentence[1:], score)
    return best


def doc_frequencies(docs: Iterable[set[str]]) -> tuple[Counter[str], int]:
    """How many documents contain each term, and how many documents there are."""
    counts: Counter[str] = Counter()
    n = 0
    for doc in docs:
        counts.update(doc)
        n += 1
    return counts, n


def distinctive_terms(
    df_game: dict[int, Counter[str]],
    n_docs: dict[int, int],
    *,
    top: int,
    min_docs: int,
    prior: float = 500.0,
    min_z: float = 2.5,
    exclude: dict[int, set[str]] | None = None,
) -> dict[int, list[tuple[str, float]]]:
    """Per game, the `top` terms with the largest log-odds z-score against all other games.

    `df_game[g][t]` is the number of game g's reviews that use term t; `n_docs[g]` the number of
    game g's reviews. Counting reviews rather than words keeps one long review from dominating.
    """
    df_all: Counter[str] = Counter()
    for counts in df_game.values():
        df_all.update(counts)
    n_all = sum(n_docs.values())
    out: dict[int, list[tuple[str, float]]] = {}
    for g, counts in df_game.items():
        n_g = n_docs[g]
        n_rest = n_all - n_g
        skip = (exclude or {}).get(g, set())
        scored = []
        for term, y in counts.items():
            if y < min_docs or term in STOPWORDS or term in GENERIC or term in skip:
                continue
            a = prior * df_all[term] / max(n_all, 1)
            y_rest = df_all[term] - y
            delta = math.log((y + a) / (n_g + prior - y - a)) - math.log(
                (y_rest + a) / (n_rest + prior - y_rest - a)
            )
            z = delta / math.sqrt(1.0 / (y + a) + 1.0 / (y_rest + a))
            if z >= min_z:
                scored.append((term, z))
        scored.sort(key=lambda tz: (-tz[1], tz[0]))
        kept: list[tuple[str, float]] = []
        stems: set[str] = set()
        for t, z in scored:
            stem = t[:-1] if t.endswith("s") and len(t) > 3 else t
            if stem in stems:
                continue  # "quests" after "quest": one idea, one chip
            stems.add(stem)
            kept.append((t, round(z, 2)))
            if len(kept) == top:
                break
        out[g] = kept
    return out


def title_words(titles: Iterable[str]) -> set[str]:
    return {t for title in titles for t in tokens(title)}


def review_evidence(
    reviews: pd.DataFrame,
    games: Sequence[dict[str, Any]],
    *,
    quotes_per_game: int = 8,
    terms_per_game: int = 30,
    max_reviews_per_game: int = 4000,
    min_docs: int = 5,
    prior: float = 500.0,
) -> dict[str, Any]:
    """Build the evidence file.

    `reviews` columns: review_id, user (hashed), game (Steam ID), hours, year, text. Only games in
    `games` (the slice, in slice order) are used. Rows without text still count for `also`; the
    loader may leave text empty past `max_reviews_per_game` to save memory.
    """
    index = {int(g["id"]): k for k, g in enumerate(games)}
    df = reviews.loc[reviews["game"].isin(list(index))].sort_values("review_id", kind="mergesort")
    also_by_user: dict[str, set[int]] = defaultdict(set)
    for user, game in zip(df["user"].tolist(), df["game"].tolist(), strict=True):
        also_by_user[user].add(index[int(game)])
    # Deterministic cap per game: the reviews with text and the smallest IDs.
    df = df.loc[df["text"].notna()]
    df = df.groupby("game", sort=True, group_keys=False).head(max_reviews_per_game)
    df_game: dict[int, Counter[str]] = defaultdict(Counter)
    n_docs: dict[int, int] = defaultdict(int)
    rows_by_game: dict[int, list[tuple[int, str, float, int | None, str]]] = defaultdict(list)
    columns = [df[c].tolist() for c in ("review_id", "user", "game", "hours", "year", "text")]
    for review_id, user, game, hours, year, text in zip(*columns, strict=True):
        gid = int(game)
        year_value = None if year is None or pd.isna(year) else int(year)
        df_game[gid].update(set(tokens(clean_text(str(text)))))
        n_docs[gid] += 1
        rows_by_game[gid].append((int(review_id), str(user), float(hours), year_value, str(text)))
    exclude = {int(g["id"]): title_words([str(g["title"])]) for g in games}
    terms = distinctive_terms(
        df_game, n_docs, top=terms_per_game, min_docs=min_docs, prior=prior, exclude=exclude
    )

    out: dict[str, Any] = {}
    for game_meta in games:
        gid = int(game_meta["id"])
        own = index[gid]
        top_terms = frozenset(t for t, _ in terms.get(gid, [])[:12])
        candidates: list[Quote] = []
        for review_id, user, hours, year, text in rows_by_game.get(gid, []):
            found = best_sentence(text, top_terms)
            if found is None:
                continue
            sentence, score = found
            also = sorted(also_by_user[user] - {own})
            total = score + 0.6 * math.log1p(max(hours, 0.0)) + 0.4 * min(len(also), 5)
            candidates.append(Quote(sentence, round(hours, 1), year, also[:80], total, review_id))
        candidates.sort(key=lambda q: (-q.score, q.review_id))
        chosen: list[Quote] = []
        seen_text: set[str] = set()
        for q in candidates:
            key = q.text.lower()
            if key in seen_text:
                continue
            seen_text.add(key)
            chosen.append(q)
            if len(chosen) == quotes_per_game:
                break
        out[str(gid)] = {
            "terms": [[t, z] for t, z in terms.get(gid, [])],
            "quotes": [
                {"text": q.text, "hours": q.hours, "year": q.year, "also": q.also} for q in chosen
            ],
        }
    return {"version": 1, "games": out}
