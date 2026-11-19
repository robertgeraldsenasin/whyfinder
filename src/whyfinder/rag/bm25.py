"""BM25 with the Lucene IDF (04_ALGORITHMS.md §A8; FR-14).

    idf(t) = ln(1 + (N − df + 0.5) / (df + 0.5))
    score(q, d) = Σ_{t∈q} idf(t) · tf(t,d)·(k1 + 1) / (tf(t,d) + k1·(1 − b + b·|d|/avgdl))

The Lucene IDF never goes negative, unlike the classic Robertson–Spärck Jones form. A query term
that occurs twice counts twice, as in Lucene. Term frequencies sit in a sparse term × document
matrix, so a query touches only its terms' postings.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp


@dataclass(frozen=True)
class Bm25:
    vocabulary: dict[str, int]
    idf: np.ndarray
    tf: sp.csr_matrix  # terms × documents
    lengths: np.ndarray
    k1: float
    b: float

    @property
    def size(self) -> int:
        return int(self.lengths.size)

    def scores(self, query: list[str]) -> np.ndarray:
        """Score of every document for a tokenised query."""
        out = np.zeros(self.size, dtype=np.float64)
        if self.size == 0:
            return out
        avgdl = float(self.lengths.mean()) or 1.0
        norm = self.k1 * (1.0 - self.b + self.b * self.lengths / avgdl)
        for term, count in Counter(query).items():
            t = self.vocabulary.get(term)
            if t is None:
                continue
            row = self.tf.getrow(t)
            docs, tf = row.indices, row.data
            out[docs] += count * self.idf[t] * tf * (self.k1 + 1.0) / (tf + norm[docs])
        return out

    def top(
        self, query: list[str], k: int, among: np.ndarray | None = None
    ) -> list[tuple[int, float]]:
        """The k best (document, score) with a positive score, ties by document number."""
        s = self.scores(query)
        docs = np.arange(self.size) if among is None else np.asarray(among, dtype=np.int64)
        docs = docs[s[docs] > 0.0]
        order = np.lexsort((docs, -s[docs]))[:k]
        return [(int(docs[i]), float(s[docs[i]])) for i in order]


def build(documents: list[list[str]], *, k1: float = 1.2, b: float = 0.75) -> Bm25:
    """Index tokenised documents; inputs are not modified."""
    if k1 < 0 or not 0.0 <= b <= 1.0:
        raise ValueError("need k1 >= 0 and 0 <= b <= 1")
    vocabulary: dict[str, int] = {}
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    for d, doc in enumerate(documents):
        for term, count in sorted(Counter(doc).items()):
            t = vocabulary.setdefault(term, len(vocabulary))
            rows.append(t)
            cols.append(d)
            vals.append(float(count))
    n = len(documents)
    tf = sp.csr_matrix((vals, (rows, cols)), shape=(len(vocabulary), n), dtype=np.float64)
    df = np.diff(tf.indptr).astype(np.float64)
    idf = np.log1p((n - df + 0.5) / (df + 0.5))
    lengths = np.array([len(doc) for doc in documents], dtype=np.float64)
    return Bm25(vocabulary=vocabulary, idf=idf, tf=tf, lengths=lengths, k1=k1, b=b)
