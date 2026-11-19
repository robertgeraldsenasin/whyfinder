"""Dense vectors for review chunks: latent semantic analysis (ADR-0010).

TF-IDF (sublinear tf, smoothed idf) → rank-k truncated SVD by the randomized range finder of
Halko, Martinsson and Tropp (SIAM Review 2011), written here, then L2 normalisation. A text's vector
is its TF-IDF row times the right singular vectors: queries and chunks are embedded the same way.
It needs no model download and no GPU, runs in seconds on the demo's 6,000 quotes, and is fully
determined by the corpus and the seed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp


def randomized_svd(
    A: sp.spmatrix | np.ndarray, k: int, *, oversample: int = 10, power: int = 2, seed: int = 0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """U (m×k), s (k), Vt (k×n) of a rank-k approximation, singular values descending."""
    m, n = A.shape
    if not 1 <= k <= min(m, n):
        raise ValueError("need 1 <= k <= min(rows, columns)")
    width = min(k + oversample, min(m, n))
    omega = np.random.default_rng(seed).standard_normal((n, width))
    Q, _ = np.linalg.qr(A @ omega)
    for _ in range(power):  # power iterations sharpen a slowly decaying spectrum
        Z, _ = np.linalg.qr(A.T @ Q)
        Q, _ = np.linalg.qr(A @ Z)
    B = np.asarray((A.T @ Q).T)
    Ub, s, Vt = np.linalg.svd(B, full_matrices=False)
    U = Q @ Ub
    # Sign convention: the largest-magnitude entry of each right vector is positive (determinism).
    flip = np.sign(Vt[np.arange(Vt.shape[0]), np.argmax(np.abs(Vt), axis=1)])
    flip[flip == 0] = 1.0
    return (U * flip)[:, :k], s[:k], (Vt * flip[:, None])[:k]


@dataclass(frozen=True)
class Lsa:
    vocabulary: dict[str, int]
    idf: np.ndarray
    components: np.ndarray  # vocabulary × k

    @property
    def dim(self) -> int:
        return int(self.components.shape[1])

    def tfidf(self, documents: list[list[str]]) -> sp.csr_matrix:
        rows: list[int] = []
        cols: list[int] = []
        vals: list[float] = []
        for d, doc in enumerate(documents):
            for term, count in Counter(doc).items():
                t = self.vocabulary.get(term)
                if t is not None:
                    rows.append(d)
                    cols.append(t)
                    vals.append((1.0 + np.log(count)) * float(self.idf[t]))
        shape = (len(documents), len(self.vocabulary))
        return sp.csr_matrix((vals, (rows, cols)), shape=shape, dtype=np.float64)

    def embed(self, documents: list[list[str]]) -> np.ndarray:
        """Unit vectors (one row per document); a document with no known word gets zeros."""
        X = np.asarray(self.tfidf(documents) @ self.components)
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        return np.asarray(
            np.divide(X, norms, out=np.zeros_like(X), where=norms > 0), dtype=np.float64
        )


def fit(documents: list[list[str]], *, dim: int = 128, min_df: int = 2, seed: int = 0) -> Lsa:
    """Learn the vocabulary (terms in at least `min_df` documents), idf and k components."""
    df: Counter[str] = Counter()
    for doc in documents:
        df.update(set(doc))
    terms = sorted(t for t, c in df.items() if c >= min_df)
    if not terms:
        raise ValueError("no term occurs in min_df documents")
    vocabulary = {t: i for i, t in enumerate(terms)}
    n = len(documents)
    idf = np.log((1.0 + n) / (1.0 + np.array([df[t] for t in terms], dtype=np.float64))) + 1.0
    empty = Lsa(vocabulary, idf, np.zeros((len(terms), 0)))
    X = empty.tfidf(documents)
    k = min(dim, min(X.shape) - 1) if min(X.shape) > 1 else 1
    _, _, Vt = randomized_svd(X, k, seed=seed)
    return Lsa(vocabulary=vocabulary, idf=idf, components=Vt.T.copy())
