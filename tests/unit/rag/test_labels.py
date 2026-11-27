"""Hand labels for review retrieval (#33): the sheet, kappa and the ranking metrics."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from whyfinder.rag.labels import (
    FIELDS,
    LabelError,
    Row,
    cohen_kappa,
    missing,
    ndcg_at,
    read,
    recall_at,
    score,
    write,
)


def test_kappa_against_hand_counts() -> None:
    a = [0, 0, 1, 1, 2, 2]
    b = [0, 1, 1, 1, 2, 0]
    # agreement 4/6, chance (2*2 + 2*3 + 2*1)/36 = 1/3, so (2/3 - 1/3) / (2/3)
    assert cohen_kappa(a, b) == pytest.approx(0.5)
    # weighted: disagreement 0.5/6 + 1/6 = 0.25 against chance 15/36
    assert cohen_kappa(a, b, weights="linear") == pytest.approx(0.4)
    assert cohen_kappa(a, a) == pytest.approx(1.0)
    assert cohen_kappa([1, 1, 1], [1, 1, 1]) == 1.0
    assert cohen_kappa([0, 2, 0, 2], [2, 0, 2, 0]) == pytest.approx(-1.0)
    with pytest.raises(ValueError, match="equally long"):
        cohen_kappa([0, 1], [0])
    with pytest.raises(ValueError, match="non-empty"):
        cohen_kappa([], [])


def test_recall_and_ndcg_against_hand_counts() -> None:
    grades = {"a": 2, "b": 1, "c": 0, "d": 2}
    ranking = ["c", "a", "b", "d"]
    assert recall_at(ranking, grades, 2) == pytest.approx(1 / 3)
    assert recall_at(ranking, grades, 5) == 1.0
    ideal = 3 + 3 / math.log2(3)
    assert ndcg_at(ranking, grades, 2) == pytest.approx((3 / math.log2(3)) / ideal)
    assert ndcg_at(["a", "d", "b", "c"], grades, 5) == pytest.approx(1.0)
    assert ndcg_at(["x", "y"], grades, 5) == 0.0  # nothing relevant retrieved
    assert recall_at(ranking, {"a": 0}, 5) is None
    assert ndcg_at(ranking, {"a": 0}, 5) is None


def rows() -> list[Row]:
    def r(q: int, c: str, a: int | None, b: int | None = None) -> Row:
        return Row(q, "620", "Portal 2", "Co-op", c, f"text {c}", a, b)

    return [
        r(1, "c1", 2, 2),
        r(1, "c2", 0, 1),
        r(1, "c3", 1, 1),
        r(2, "c4", 0),
        r(2, "c5", 2),
        r(3, "c6", None),
        r(3, "c7", 1),
    ]


def test_the_sheet_round_trips_and_reports_what_is_missing(tmp_path: Path) -> None:
    path = tmp_path / "labels.csv"
    write(path, rows())
    assert path.read_text().splitlines()[0] == ",".join(FIELDS)
    assert read(path) == rows()
    assert missing(rows(), double=1) == (1, 0)
    assert missing(rows(), double=2) == (1, 2)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("query,app_id\n1,620\n", "columns"),
        (",".join(FIELDS) + "\n1,620,P,Co-op,c1,t,3,\n", "0, 1 or 2"),
        (",".join(FIELDS) + "\nx,620,P,Co-op,c1,t,1,\n", "query must be a number"),
        (
            ",".join(FIELDS) + "\n1,620,P,a,c1,t,1,\n2,620,P,a,c2,t,1,\n1,620,P,a,c3,t,1,\n",
            "together",
        ),
        (",".join(FIELDS) + "\n1,620,P,a,c1,t,1,\n1,620,P,a,c1,t,0,\n", "twice"),
    ],
)
def test_a_malformed_sheet_is_refused(tmp_path: Path, body: str, message: str) -> None:
    path = tmp_path / "labels.csv"
    path.write_text(body)
    with pytest.raises(LabelError, match=message):
        read(path)


def test_score_uses_fully_graded_queries_and_both_labellers_for_kappa() -> None:
    rankings = {
        "good": {1: ["c1", "c3", "c2"], 2: ["c5", "c4"], 3: ["c7", "c6"]},
        "bad": {1: ["c2"], 2: ["c4"]},
    }
    report = score(rows(), rankings, k=1)
    assert report["queries_labelled"] == 2  # query 3 still has a blank grade
    assert report["queries_with_relevant_reviews"] == 2
    assert report["reviews_labelled"] == 5
    assert report["double_labelled_reviews"] == 3
    assert report["kappa"] == pytest.approx(cohen_kappa([2, 0, 1], [2, 1, 1]))
    systems = report["systems"]
    assert isinstance(systems, dict)
    assert systems["good"] == {"queries": 2, "recall_at_1": 0.75, "ndcg_at_1": 1.0}
    assert systems["bad"] == {"queries": 2, "recall_at_1": 0.0, "ndcg_at_1": 0.0}
