"""The heterogeneous game graph (FR-06; docs/spec/04_ALGORITHMS.md §A4).

Nodes, in this order: games (catalogue order), then tags, developers and publishers (each sorted by
name). Undirected weighted edges:

| Edge | Weight |
| --- | --- |
| game–tag | γ_tag · idf(tag), top `tags_per_game` tags of each game, idf(t) = ln(1 + n / df(t)) |
| game–developer | γ_dev |
| game–publisher | γ_pub |
| game–game | γ_co · cosine(G), each game's `coplay_per_game` most co-played games, made symmetric |

Stored as CSR with neighbours in ascending node order. Weighted degrees are summed in that order,
so the browser engine reproduces them exactly.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GameInfo:
    """What the graph needs to know about one game."""

    tags: Sequence[str]
    developer: str | None
    publisher: str | None


@dataclass(frozen=True)
class Weights:
    """Edge-type weights γ (params.yaml: graph.weights)."""

    tag: float = 1.0
    developer: float = 1.0
    publisher: float = 0.5
    coplay: float = 1.0


@dataclass(frozen=True)
class Graph:
    """CSR adjacency plus node labels. Node i < n_games is game i of the catalogue."""

    n_games: int
    kinds: list[str]  # "game" | "tag" | "developer" | "publisher"
    names: list[str]
    indptr: np.ndarray
    indices: np.ndarray
    weights: np.ndarray
    degree: np.ndarray

    @property
    def n_nodes(self) -> int:
        return len(self.kinds)

    def neighbours(self, v: int) -> tuple[np.ndarray, np.ndarray]:
        start, end = self.indptr[v], self.indptr[v + 1]
        return self.indices[start:end], self.weights[start:end]


def tag_idf(games: Sequence[GameInfo], tags_per_game: int) -> dict[str, float]:
    """idf(t) = ln(1 + n / df(t)) over the games' top tags."""
    df: dict[str, int] = {}
    for game in games:
        for tag in dict.fromkeys(game.tags[:tags_per_game]):
            df[tag] = df.get(tag, 0) + 1
    n = len(games)
    return {tag: math.log(1.0 + n / count) for tag, count in sorted(df.items())}


def coplay_neighbours(S: np.ndarray, per_game: int) -> list[list[int]]:
    """Each game's `per_game` most co-played games (cosine > 0), ties by index."""
    n = S.shape[0]
    out: list[list[int]] = []
    columns = np.arange(n)
    for i in range(n):
        row = S[i].copy()
        row[i] = 0.0
        order = np.lexsort((columns, -row))
        out.append([int(j) for j in order[:per_game] if row[j] > 0.0])
    return out


def build_graph(
    games: Sequence[GameInfo],
    S: np.ndarray,
    *,
    weights: Weights,
    tags_per_game: int,
    coplay_per_game: int,
) -> Graph:
    """Build the graph from catalogue info and the co-play cosine matrix S (n × n)."""
    n = len(games)
    if S.shape != (n, n):
        raise ValueError(f"S must be {n} × {n}, got {S.shape}")
    idf = tag_idf(games, tags_per_game)
    developers = sorted({g.developer for g in games if g.developer})
    publishers = sorted({g.publisher for g in games if g.publisher})
    kinds = ["game"] * n + ["tag"] * len(idf) + ["developer"] * len(developers)
    kinds += ["publisher"] * len(publishers)
    names = [f"game:{i}" for i in range(n)] + list(idf) + developers + publishers
    tag_node = {tag: n + k for k, tag in enumerate(idf)}
    dev_node = {d: n + len(idf) + k for k, d in enumerate(developers)}
    pub_node = {p: n + len(idf) + len(developers) + k for k, p in enumerate(publishers)}

    edges: dict[tuple[int, int], float] = {}

    def add(a: int, b: int, w: float) -> None:
        if a == b or w <= 0.0:
            return
        key = (min(a, b), max(a, b))
        edges[key] = max(edges.get(key, 0.0), w)

    for i, game in enumerate(games):
        for tag in dict.fromkeys(game.tags[:tags_per_game]):
            add(i, tag_node[tag], weights.tag * idf[tag])
        if game.developer:
            add(i, dev_node[game.developer], weights.developer)
        if game.publisher:
            add(i, pub_node[game.publisher], weights.publisher)
    for i, neighbours in enumerate(coplay_neighbours(S, coplay_per_game)):
        for j in neighbours:
            add(i, j, weights.coplay * float(S[i, j]))

    adjacency: list[list[tuple[int, float]]] = [[] for _ in kinds]
    for (a, b), w in edges.items():
        adjacency[a].append((b, w))
        adjacency[b].append((a, w))
    indptr = [0]
    indices: list[int] = []
    values: list[float] = []
    degree: list[float] = []
    for row in adjacency:
        row.sort()
        total = 0.0
        for v, w in row:
            indices.append(v)
            values.append(w)
            total += w
        degree.append(total)
        indptr.append(len(indices))
    return Graph(
        n_games=n,
        kinds=kinds,
        names=names,
        indptr=np.array(indptr, dtype=np.int64),
        indices=np.array(indices, dtype=np.int64),
        weights=np.array(values, dtype=np.float64),
        degree=np.array(degree, dtype=np.float64),
    )


def check_graph(graph: Graph) -> None:
    """Graph contract: symmetric, weights > 0, no self-loops, every game linked to something."""
    for v in range(graph.n_nodes):
        neighbours, w = graph.neighbours(v)
        if np.any(w <= 0.0):
            raise ValueError(f"node {v}: non-positive edge weight")
        if np.any(neighbours == v):
            raise ValueError(f"node {v}: self-loop")
        if np.any(np.diff(neighbours) <= 0):
            raise ValueError(f"node {v}: neighbours not strictly ascending")
        for u, weight in zip(neighbours.tolist(), w.tolist(), strict=True):
            back, back_w = graph.neighbours(u)
            k = int(np.searchsorted(back, v))
            if k >= len(back) or back[k] != v or back_w[k] != weight:
                raise ValueError(f"edge {v}–{u} is not symmetric")
    for g in range(graph.n_games):
        if graph.indptr[g + 1] == graph.indptr[g]:
            raise ValueError(f"game {g} has no edges")
