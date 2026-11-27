"""Hand labels for review retrieval (#33; 06_RAG "Evaluation"; docs/labelling/retrieval.md).

A query is what grounding asks the review index: one aspect (a shared tag or a word both games'
players use), searched within one recommended game's reviews. Every review of that game is
labelled for the aspect, so the judgments are complete and no ranking chose what got labelled:

- 2: the review talks about the aspect; it would make a good quote for it;
- 1: it touches the aspect in passing, or only implies it;
- 0: it is not about the aspect.

`label_a` is the primary labeller's grade and the one the metrics use; the first `DOUBLE` queries
also carry `label_b` from a second labeller, for Cohen's kappa. Rankings are scored by Recall@5
(a review counts as relevant at grade 1 or more) and nDCG@5 (gain 2^grade - 1), per query, then
averaged over the queries that have any relevant review.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

GRADES: Final = (0, 1, 2)
DOUBLE: Final = 30
QUERIES: Final = 150
FIELDS: Final = ("query", "app_id", "game", "aspect", "chunk_id", "text", "label_a", "label_b")


@dataclass(frozen=True)
class Row:
    query: int
    app_id: str
    game: str
    aspect: str
    chunk_id: str
    text: str
    label_a: int | None
    label_b: int | None


class LabelError(ValueError):
    """The label file is malformed: wrong columns, a grade outside 0-2, a query split up."""


def grade(raw: str, where: str) -> int | None:
    value = raw.strip()
    if not value:
        return None
    if value not in {str(g) for g in GRADES}:
        raise LabelError(f"{where}: a grade is 0, 1 or 2, not {raw!r}")
    return int(value)


def read(path: Path) -> list[Row]:
    """The rows of a label file, checked for shape; blank grades read as None."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise LabelError(f"{path}: the columns must be {', '.join(FIELDS)}")
        rows: list[Row] = []
        for n, raw in enumerate(reader, start=2):
            where = f"{path}:{n}"
            try:
                query = int(raw["query"])
            except ValueError as exc:
                raise LabelError(f"{where}: query must be a number") from exc
            rows.append(
                Row(
                    query=query,
                    app_id=raw["app_id"],
                    game=raw["game"],
                    aspect=raw["aspect"],
                    chunk_id=raw["chunk_id"],
                    text=raw["text"],
                    label_a=grade(raw["label_a"], where),
                    label_b=grade(raw["label_b"], where),
                )
            )
    seen: set[int] = set()
    last: int | None = None
    for row in rows:
        if row.query != last:
            if row.query in seen:
                raise LabelError(f"{path}: the rows of query {row.query} must be together")
            seen.add(row.query)
            last = row.query
    keys = [(r.query, r.chunk_id) for r in rows]
    if len(set(keys)) != len(keys):
        raise LabelError(f"{path}: a review appears twice in one query")
    return rows


def write(path: Path, rows: Sequence[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow(FIELDS)
        for r in rows:
            out.writerow(
                [
                    r.query,
                    r.app_id,
                    r.game,
                    r.aspect,
                    r.chunk_id,
                    r.text,
                    "" if r.label_a is None else r.label_a,
                    "" if r.label_b is None else r.label_b,
                ]
            )


def missing(rows: Sequence[Row], *, double: int = DOUBLE) -> tuple[int, int]:
    """Blank primary grades, and blank second grades among the first `double` queries."""
    a = sum(1 for r in rows if r.label_a is None)
    b = sum(1 for r in rows if r.query <= double and r.label_b is None)
    return a, b


def cohen_kappa(
    a: Sequence[int], b: Sequence[int], *, weights: Literal["none", "linear"] = "none"
) -> float:
    """Cohen's kappa between two labellers over the same items, unweighted or with linear weights
    for the ordered grades. 1 when they agree as well as possible; 0 at chance."""
    if len(a) != len(b) or not a:
        raise ValueError("kappa needs two equally long, non-empty label lists")
    cats = GRADES
    k = len(cats)
    n = len(a)
    observed = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b, strict=True):
        observed[cats.index(x)][cats.index(y)] += 1 / n
    pa = [sum(row) for row in observed]
    pb = [sum(observed[i][j] for i in range(k)) for j in range(k)]

    def w(i: int, j: int) -> float:
        if weights == "none":
            return 0.0 if i == j else 1.0
        return abs(i - j) / (k - 1)

    disagree = sum(w(i, j) * observed[i][j] for i in range(k) for j in range(k))
    chance = sum(w(i, j) * pa[i] * pb[j] for i in range(k) for j in range(k))
    if chance == 0.0:
        return 1.0  # both labellers used one and the same grade throughout
    return 1.0 - disagree / chance


def recall_at(ranking: Sequence[str], grades: Mapping[str, int], k: int) -> float | None:
    """Share of the relevant reviews (grade >= 1) in the first k; None when there are none."""
    relevant = {c for c, g in grades.items() if g >= 1}
    if not relevant:
        return None
    return len(relevant.intersection(ranking[:k])) / len(relevant)


def ndcg_at(ranking: Sequence[str], grades: Mapping[str, int], k: int) -> float | None:
    """nDCG@k with gain 2^grade - 1 and log2 discounts; None when nothing is relevant."""

    def dcg(gs: Sequence[int]) -> float:
        return sum((2.0**g - 1.0) / math.log2(r + 2) for r, g in enumerate(gs[:k]))

    ideal = dcg(sorted(grades.values(), reverse=True))
    if ideal == 0.0:
        return None
    return dcg([grades.get(c, 0) for c in ranking]) / ideal


def by_query(rows: Sequence[Row]) -> dict[int, dict[str, int]]:
    """The primary grades of each fully labelled query."""
    out: dict[int, dict[str, int]] = {}
    for q in sorted({r.query for r in rows}):
        mine = [r for r in rows if r.query == q]
        if all(r.label_a is not None for r in mine):
            out[q] = {r.chunk_id: int(r.label_a) for r in mine if r.label_a is not None}
    return out


def score(
    rows: Sequence[Row], rankings: Mapping[str, Mapping[int, Sequence[str]]], *, k: int = 5
) -> dict[str, object]:
    """Recall@k and nDCG@k per ranking system, and kappa over the double-labelled reviews.
    `rankings[system][query]` is that system's order of the query's reviews, best first."""
    graded = by_query(rows)
    systems: dict[str, dict[str, float | int | None]] = {}
    for name, ranked in sorted(rankings.items()):
        recalls = [recall_at(ranked[q], g, k) for q, g in graded.items() if q in ranked]
        ndcgs = [ndcg_at(ranked[q], g, k) for q, g in graded.items() if q in ranked]
        r = [x for x in recalls if x is not None]
        d = [x for x in ndcgs if x is not None]
        systems[name] = {
            "queries": len(r),
            f"recall_at_{k}": sum(r) / len(r) if r else None,
            f"ndcg_at_{k}": sum(d) / len(d) if d else None,
        }
    pairs = [
        (r.label_a, r.label_b) for r in rows if r.label_a is not None and r.label_b is not None
    ]
    a = [int(x) for x, _ in pairs]
    b = [int(y) for _, y in pairs]
    return {
        "queries_labelled": len(graded),
        "queries_with_relevant_reviews": sum(1 for g in graded.values() if any(g.values())),
        "reviews_labelled": sum(len(g) for g in graded.values()),
        "double_labelled_reviews": len(pairs),
        "kappa": cohen_kappa(a, b) if pairs else None,
        "kappa_linear": cohen_kappa(a, b, weights="linear") if pairs else None,
        "systems": systems,
    }
