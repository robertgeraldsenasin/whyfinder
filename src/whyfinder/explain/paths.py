"""Graph paths for "related by" explanations (FR-13): what a pick and one of your games share.

A path is either a direct co-play edge or a two-step path through a shared tag, developer or
publisher. Paths are ranked by the weight of the weaker edge (rarer tags weigh more, via idf), ties
by node ID. Every returned path exists in the graph by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

from whyfinder.graph.build import Graph


@dataclass(frozen=True)
class Path:
    """`via` is the shared node (or None for a direct co-play edge)."""

    source: int
    target: int
    via: int | None
    kind: str  # "co-play" | "tag" | "developer" | "publisher"
    weight: float


def related_by(graph: Graph, source: int, target: int, *, limit: int = 2) -> list[Path]:
    """Up to `limit` paths between two games, strongest first."""
    a_nodes, a_w = graph.neighbours(source)
    b_nodes, b_w = graph.neighbours(target)
    a = dict(zip(a_nodes.tolist(), a_w.tolist(), strict=True))
    b = dict(zip(b_nodes.tolist(), b_w.tolist(), strict=True))
    paths: list[Path] = []
    if target in a:
        paths.append(Path(source, target, None, "co-play", a[target]))
    for node in sorted(a.keys() & b.keys()):
        if node < graph.n_games:
            continue
        paths.append(Path(source, target, node, graph.kinds[node], min(a[node], b[node])))
    paths.sort(key=lambda p: (-p.weight, -1 if p.via is None else p.via))
    return paths[:limit]
