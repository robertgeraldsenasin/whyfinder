from __future__ import annotations

import math

import numpy as np
import pytest

from whyfinder.eval import metrics
from whyfinder.rerank.dpp import tfidf_vectors


def test_ndcg_by_hand() -> None:
    # Hits at ranks 1 and 3, two relevant games: DCG = 1 + 1/log2(4); IDCG = 1 + 1/log2(3).
    value = metrics.ndcg_at([[5, 7, 9, 2]], [{5, 9}], 10)[0]
    assert value == pytest.approx((1 + 1 / 2) / (1 + 1 / math.log2(3)))
    assert metrics.ndcg_at([[5, 9]], [{5, 9}], 10)[0] == pytest.approx(1.0)
    assert metrics.ndcg_at([[1, 2]], [set()], 10)[0] == 0.0
    # Only the first k count, and the ideal is capped at k hits.
    assert metrics.ndcg_at([[1, 2, 3]], [{3}], 2)[0] == 0.0
    assert metrics.ndcg_at([[1, 2]], [{1, 2, 3, 4}], 2)[0] == pytest.approx(1.0)


def test_recall_and_mrr_by_hand() -> None:
    ranked = [[1, 2, 3, 4], [9, 8], [7]]
    relevant = [{2, 4, 6}, set(), {5}]
    assert metrics.recall_at(ranked, relevant, 2).tolist() == [1 / 3, 0.0, 0.0]
    assert metrics.recall_at(ranked, relevant, 20).tolist() == [2 / 3, 0.0, 0.0]
    assert metrics.mrr(ranked, relevant).tolist() == [0.5, 0.0, 0.0]


def test_coverage_counts_distinct_games_in_the_first_k() -> None:
    assert metrics.coverage([[0, 1, 2], [1, 3]], 10, 2) == 0.3
    with pytest.raises(ValueError, match="n_items"):
        metrics.coverage([[0]], 0, 1)


def test_ild_is_one_minus_mean_pairwise_tag_cosine() -> None:
    vectors = tfidf_vectors([["a"], ["a"], ["b"]])
    assert metrics.ild([[0, 1]], vectors, 10)[0] == pytest.approx(0.0)
    assert metrics.ild([[0, 2]], vectors, 10)[0] == pytest.approx(1.0)
    assert metrics.ild([[0, 1, 2]], vectors, 10)[0] == pytest.approx(1 - 1 / 3)
    assert metrics.ild([[0]], vectors, 10)[0] == 0.0


def test_arp_is_the_mean_popularity_of_the_list() -> None:
    pop = np.array([1.0, 0.5, 0.0, 0.25])
    assert metrics.arp([[0, 1], [2, 3], []], pop, 10).tolist() == [0.75, 0.125, 0.0]


def test_k_out_of_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="k must be"):
        metrics.ndcg_at([[1]], [{1}], 0)
    with pytest.raises(ValueError, match="k must be"):
        metrics.recall_at([[1]], [{1}], 500)
    with pytest.raises(ValueError, match="shorter"):
        metrics.ndcg_at([[1], [2]], [{1}], 10)  # misaligned users
