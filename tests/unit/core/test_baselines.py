from __future__ import annotations

import numpy as np
import pytest
import scipy.sparse as sp

from whyfinder.core.baselines import gram, item_knn, popularity


def random_matrix(m: int, n: int, density: float, seed: int) -> sp.csr_matrix:
    rng = np.random.default_rng(seed)
    X = sp.random(m, n, density=density, random_state=rng, format="csr")
    X.data = 1.0 + rng.random(X.nnz) * 4.0
    return X


def test_popularity_is_summed_confidence() -> None:
    X = sp.csr_matrix(np.array([[1.0, 0.0, 2.5], [0.0, 0.0, 1.0], [3.0, 0.0, 0.0]]))
    assert popularity(X).tolist() == [4.0, 0.0, 3.5]


def test_gram_counts_co_occurrence_on_the_binary_pattern() -> None:
    X = sp.csr_matrix(np.array([[2.0, 0.0, 5.0], [1.0, 3.0, 1.0]]))
    G = gram(X)
    assert G.tolist() == [[2.0, 1.0, 2.0], [1.0, 1.0, 1.0], [2.0, 1.0, 2.0]]
    assert X.data.tolist() == [2.0, 5.0, 1.0, 3.0, 1.0]  # input untouched


def test_item_knn_matches_the_dense_formula_on_1000_items() -> None:
    X = random_matrix(3000, 1000, 0.01, seed=3)
    G = gram(X)
    s, k = 10.0, 100
    S = item_knn(G, shrinkage=s, top_k=k)
    norms = np.sqrt(np.diag(G))
    dense = G / (np.outer(norms, norms) + s)
    np.fill_diagonal(dense, 0.0)
    assert np.all(np.diag(S) == 0.0)
    assert int(np.max(np.count_nonzero(S, axis=1))) <= k
    kept = S != 0.0
    assert np.max(np.abs(S[kept] - dense[kept])) < 1e-12
    # Every kept entry is at least as large as every dropped one in its row.
    for i in range(0, 1000, 97):
        row = dense[i]
        if kept[i].any() and (~kept[i]).any():
            assert row[kept[i]].min() >= row[~kept[i] & (np.arange(1000) != i)].max() - 1e-15


def test_shrinkage_damps_rare_pairs() -> None:
    # Two pairs with the same cosine (1.0): seen together 2 times and 200 times.
    G = np.diag([2.0, 2.0, 200.0, 200.0])
    G[0, 1] = G[1, 0] = 2.0
    G[2, 3] = G[3, 2] = 200.0
    S = item_knn(G, shrinkage=10.0, top_k=3)
    assert S[2, 3] > S[0, 1] > 0.0
    assert item_knn(G, shrinkage=0.0, top_k=3)[0, 1] == pytest.approx(1.0)


def test_item_knn_rejects_bad_input() -> None:
    with pytest.raises(ValueError, match="square"):
        item_knn(np.zeros((2, 3)), shrinkage=1.0, top_k=1)
    with pytest.raises(ValueError, match="shrinkage"):
        item_knn(np.eye(2), shrinkage=-1.0, top_k=1)
    with pytest.raises(ValueError, match="top_k"):
        item_knn(np.eye(2), shrinkage=1.0, top_k=0)
