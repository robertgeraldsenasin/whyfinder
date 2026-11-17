from __future__ import annotations

import numpy as np
import pytest

from whyfinder.graph.build import GameInfo, Graph, Weights, build_graph, check_graph, tag_idf
from whyfinder.graph.ppr import keep_top, pi_matrix, pi_row, pi_rows, push


def random_graph(n: int, seed: int, avg_degree: int = 8) -> Graph:
    """A connected random weighted graph (ring + random chords), as a Graph."""
    rng = np.random.default_rng(seed)
    edges: dict[tuple[int, int], float] = {}
    for v in range(n):
        edges[(v, (v + 1) % n) if v < (v + 1) % n else ((v + 1) % n, v)] = float(
            rng.uniform(0.5, 2)
        )
    for _ in range(n * avg_degree // 2):
        a, b = sorted(rng.choice(n, 2, replace=False).tolist())
        edges[(a, b)] = float(rng.uniform(0.1, 3.0))
    adjacency: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    for (a, b), w in edges.items():
        adjacency[a].append((b, w))
        adjacency[b].append((a, w))
    indptr, indices, weights, degree = [0], [], [], []
    for row in adjacency:
        row.sort()
        total = 0.0
        for u, w in row:
            indices.append(u)
            weights.append(w)
            total += w
        degree.append(total)
        indptr.append(len(indices))
    return Graph(
        n_games=n,
        kinds=["game"] * n,
        names=[str(i) for i in range(n)],
        indptr=np.array(indptr),
        indices=np.array(indices),
        weights=np.array(weights),
        degree=np.array(degree),
    )


def power_iteration(graph: Graph, seed: int, alpha: float) -> np.ndarray:
    n = graph.n_nodes
    W = np.zeros((n, n))
    for v in range(n):
        nb, w = graph.neighbours(v)
        W[v, nb] = w
    P = W / W.sum(axis=1, keepdims=True)
    e = np.zeros(n)
    e[seed] = 1.0
    pi = e.copy()
    for _ in range(10_000):
        nxt = alpha * e + (1 - alpha) * pi @ P
        if np.abs(nxt - pi).max() < 1e-14:
            return nxt
        pi = nxt
    raise AssertionError("power iteration did not converge")


@pytest.mark.parametrize("eps", [1e-4, 1e-6])
def test_push_matches_power_iteration_within_eps_degree(eps: float) -> None:
    graph = random_graph(2000, seed=3)
    for seed in (0, 777):
        result = push(graph, seed, alpha=0.15, eps=eps)
        exact = power_iteration(graph, seed, 0.15)
        error = exact - result.p
        assert np.all(error >= -1e-12)  # push underestimates
        assert np.all(error <= eps * graph.degree + 1e-12)
        assert result.p.sum() <= 1.0 + 1e-12
        assert result.p.sum() + result.residual_mass == pytest.approx(1.0)
        assert result.rounds > 0
        assert result.pushes >= result.rounds


def test_push_is_deterministic_and_rejects_bad_arguments() -> None:
    graph = random_graph(50, seed=1)
    a = push(graph, 3, alpha=0.2, eps=1e-6).p
    assert np.array_equal(a, push(graph, 3, alpha=0.2, eps=1e-6).p)
    with pytest.raises(ValueError, match="alpha"):
        push(graph, 0, alpha=1.0, eps=1e-6)
    with pytest.raises(ValueError, match="eps"):
        push(graph, 0, alpha=0.2, eps=0.0)
    with pytest.raises(ValueError, match="seed"):
        push(graph, 50, alpha=0.2, eps=1e-6)


def test_isolated_node_keeps_its_mass() -> None:
    graph = Graph(
        n_games=1,
        kinds=["game"],
        names=["g"],
        indptr=np.array([0, 0]),
        indices=np.array([], dtype=np.int64),
        weights=np.array([]),
        degree=np.array([0.0]),
    )
    assert push(graph, 0, alpha=0.15, eps=1e-6).p.tolist() == [1.0]


def test_pi_rows_exclude_the_seed_and_keep_top_m() -> None:
    graph = random_graph(30, seed=9)
    row = pi_row(graph, 4, alpha=0.15, eps=1e-7, top_m=5)
    assert row[4] == 0.0
    assert np.count_nonzero(row) == 5
    Pi = pi_matrix(graph, alpha=0.15, eps=1e-7, top_m=5)
    assert np.array_equal(Pi[4], row)
    full, loss = pi_rows(graph, alpha=0.15, eps=1e-7, top_m=29)
    assert np.all(loss == 0.0)  # nothing truncated when every game is kept
    _, loss5 = pi_rows(graph, alpha=0.15, eps=1e-7, top_m=5)
    assert np.all((loss5 > 0.0) & (loss5 < 1.0))
    assert np.count_nonzero(full[4]) == 29
    assert keep_top(np.array([1.0, 3.0, 3.0, 0.0]), 2).tolist() == [0.0, 3.0, 3.0, 0.0]
    assert keep_top(np.array([0.0, -1.0, 2.0]), 3).tolist() == [0.0, 0.0, 2.0]


def games() -> list[GameInfo]:
    return [
        GameInfo(["Roguelike", "Action", "Indie"], "Supergiant", "Supergiant"),
        GameInfo(["Roguelike", "Metroidvania"], "Motion Twin", None),
        GameInfo(["Metroidvania", "Action"], "Team Cherry", "Team Cherry"),
        GameInfo(["Puzzle"], None, "Team Cherry"),
    ]


def test_build_graph_nodes_edges_and_contract() -> None:
    S = np.array(
        [[0, 0.5, 0.2, 0], [0.5, 0, 0.4, 0], [0.2, 0.4, 0, 0.1], [0, 0, 0.1, 0]], dtype=float
    )
    graph = build_graph(games(), S, weights=Weights(), tags_per_game=20, coplay_per_game=1)
    check_graph(graph)
    assert graph.kinds[:4] == ["game"] * 4
    assert graph.names[4:9] == ["Action", "Indie", "Metroidvania", "Puzzle", "Roguelike"]
    assert graph.kinds.count("developer") == 3
    assert graph.kinds.count("publisher") == 2
    idf = tag_idf(games(), 20)
    assert idf["Puzzle"] == pytest.approx(np.log(1 + 4 / 1))
    nb, w = graph.neighbours(0)
    assert 1 in nb.tolist()  # co-play: game 0's best partner is game 1
    assert w[nb.tolist().index(1)] == pytest.approx(0.5)
    nb3, _ = graph.neighbours(3)
    assert 2 in nb3.tolist()  # game 3's best partner is 2; edges are symmetric
    assert graph.degree[0] == pytest.approx(w.sum())
    with pytest.raises(ValueError, match="must be 4"):
        build_graph(
            games(), np.zeros((3, 3)), weights=Weights(), tags_per_game=5, coplay_per_game=1
        )


def test_check_graph_rejects_isolated_games_and_bad_edges() -> None:
    lonely = build_graph(
        [GameInfo([], None, None), GameInfo(["a"], None, None)],
        np.zeros((2, 2)),
        weights=Weights(),
        tags_per_game=5,
        coplay_per_game=1,
    )
    with pytest.raises(ValueError, match="no edges"):
        check_graph(lonely)
    graph = random_graph(5, seed=2)
    broken = Graph(**{**graph.__dict__, "weights": graph.weights.copy()})
    broken.weights[0] = -1.0
    with pytest.raises(ValueError, match="non-positive"):
        check_graph(broken)
    asym = Graph(**{**graph.__dict__, "weights": graph.weights.copy()})
    asym.weights[0] = asym.weights[0] + 1.0
    with pytest.raises(ValueError, match="symmetric"):
        check_graph(asym)
