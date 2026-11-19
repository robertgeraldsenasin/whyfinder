"""Hierarchical navigable small-world graph (04_ALGORITHMS.md §A9; Malkov and Yashunin, TPAMI 2020).

Approximate nearest neighbours by inner product over L2-normalised vectors (distance 1 − u·v).
Each vector gets a level ⌊−ln(U)·m_L⌋ with m_L = 1/ln M from a seeded generator, so a build is
reproducible. Search descends the upper layers greedily and runs a best-first search of width ef
at layer 0. Neighbours are chosen with the paper's heuristic (Algorithm 4), which keeps a candidate
only if it is closer to the new vector than to every neighbour already kept; layer 0 keeps up to
2M links, the others M. Every tie is broken by vector number.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Hnsw:
    vectors: np.ndarray
    m: int = 16
    ef_construction: int = 200
    seed: int = 0
    links: list[list[list[int]]] = field(default_factory=list)  # links[node][layer]
    entry: int = -1
    top: int = -1

    @property
    def size(self) -> int:
        return len(self.links)

    def _cap(self, layer: int) -> int:
        return 2 * self.m if layer == 0 else self.m

    def _distances(self, q: np.ndarray, nodes: list[int]) -> np.ndarray:
        return np.asarray(1.0 - self.vectors[nodes] @ q, dtype=np.float64)

    def _greedy(self, q: np.ndarray, start: int, layer: int) -> int:
        best, best_d = start, float(1.0 - self.vectors[start] @ q)
        improved = True
        while improved:
            improved = False
            nbrs = self.links[best][layer]
            if not nbrs:
                break
            d = self._distances(q, nbrs)
            for node, dist in zip(nbrs, d, strict=True):
                if (dist, node) < (best_d, best):
                    best, best_d, improved = node, float(dist), True
        return best

    def _search_layer(
        self, q: np.ndarray, starts: list[int], ef: int, layer: int
    ) -> list[tuple[float, int]]:
        """The ef nearest found from `starts` on one layer, as (distance, node), nearest first."""
        visited = set(starts)
        d0 = self._distances(q, starts)
        candidates = [(float(d), s) for d, s in zip(d0, starts, strict=True)]
        heapq.heapify(candidates)
        found = [(-d, -s) for d, s in candidates]  # max-heap on (distance, node)
        heapq.heapify(found)
        while len(found) > ef:
            heapq.heappop(found)
        while candidates:
            dist, node = heapq.heappop(candidates)
            worst = (-found[0][0], -found[0][1])
            if (dist, node) > worst and len(found) >= ef:
                break
            fresh = [n for n in self.links[node][layer] if n not in visited]
            if not fresh:
                continue
            visited.update(fresh)
            for n, dn in zip(fresh, self._distances(q, fresh), strict=True):
                d = float(dn)
                worst = (-found[0][0], -found[0][1])
                if len(found) < ef or (d, n) < worst:
                    heapq.heappush(candidates, (d, n))
                    heapq.heappush(found, (-d, -n))
                    if len(found) > ef:
                        heapq.heappop(found)
        return sorted((-d, -n) for d, n in found)

    def _select(
        self, base: np.ndarray, candidates: list[tuple[float, int]], keep: int
    ) -> list[int]:
        """Algorithm 4: nearest first, skip a candidate closer to a kept neighbour than to base."""
        ordered = sorted(candidates)
        if len(ordered) <= 1:
            return [n for _, n in ordered][:keep]
        nodes = [n for _, n in ordered]
        between = 1.0 - self.vectors[nodes] @ self.vectors[nodes].T  # one product for all pairs
        chosen: list[int] = []
        for i, (dist, _) in enumerate(ordered):
            if len(chosen) == keep:
                break
            if chosen and float(between[i, chosen].min()) < dist:
                continue
            chosen.append(i)
        return [nodes[i] for i in chosen]

    def add(self, level: int) -> None:
        """Insert the next vector (number `size`) at the given level."""
        node = self.size
        q = self.vectors[node]
        self.links.append([[] for _ in range(level + 1)])
        if self.entry < 0:
            self.entry, self.top = node, level
            return
        ep = self.entry
        for layer in range(self.top, level, -1):
            ep = self._greedy(q, ep, layer)
        starts = [ep]
        for layer in range(min(level, self.top), -1, -1):
            found = self._search_layer(q, starts, self.ef_construction, layer)
            chosen = self._select(q, found, self.m)
            self.links[node][layer] = chosen
            for other in chosen:
                mine = self.links[other][layer]
                mine.append(node)
                if len(mine) > self._cap(layer):
                    base = self.vectors[other]
                    pool = list(zip(self._distances(base, mine).tolist(), mine, strict=True))
                    self.links[other][layer] = self._select(base, pool, self._cap(layer))
            starts = [n for _, n in found]
        if level > self.top:
            self.entry, self.top = node, level

    def search(self, q: np.ndarray, k: int, ef: int = 64) -> list[tuple[int, float]]:
        """The k nearest (vector number, similarity), most similar first."""
        if self.entry < 0 or k < 1:
            return []
        ep = self.entry
        for layer in range(self.top, 0, -1):
            ep = self._greedy(q, ep, layer)
        found = self._search_layer(q, [ep], max(ef, k), 0)
        return [(n, 1.0 - d) for d, n in found[:k]]


def levels(n: int, m: int, seed: int) -> list[int]:
    """⌊−ln(U)·m_L⌋ for each vector, m_L = 1/ln m, from one seeded generator."""
    u = np.random.default_rng(seed).random(n)
    u = np.where(u == 0.0, np.finfo(np.float64).tiny, u)
    return [int(x) for x in np.floor(-np.log(u) / math.log(m))]


def build(vectors: np.ndarray, *, m: int = 16, ef_construction: int = 200, seed: int = 0) -> Hnsw:
    """Index unit-length rows of `vectors` (copied, so the input is never changed)."""
    if vectors.ndim != 2:
        raise ValueError("vectors must be a 2-D array")
    if m < 2 or ef_construction < 1:
        raise ValueError("need m >= 2 and ef_construction >= 1")
    index = Hnsw(
        np.array(vectors, dtype=np.float64), m=m, ef_construction=ef_construction, seed=seed
    )
    for level in levels(len(vectors), m, seed):
        index.add(level)
    return index


def exact(vectors: np.ndarray, q: np.ndarray, k: int) -> list[tuple[int, float]]:
    """Brute-force top k by inner product, ties by vector number (the oracle for recall)."""
    sims = vectors @ q
    order = np.lexsort((np.arange(len(sims)), -sims))[:k]
    return [(int(i), float(sims[i])) for i in order]
