"""Model constants and golden outputs for the browser engine (ADR-0015).

`build_model` runs the Python core on the demo slice: EASE^R on G, the game graph and Π by push, the
scale constants, then the full pipeline for a few fixed histories. `goldens` records what the
TypeScript engine must reproduce: scores, attributions and Π rows within 1e-9, and identical
candidates, picks, variety flags and counterfactual sets.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from whyfinder.core.blend import blend, confidence, scale_constant
from whyfinder.core.ease import ease
from whyfinder.explain.attributions import attributions
from whyfinder.explain.counterfactual import greedy
from whyfinder.explain.paths import related_by
from whyfinder.export.demo import cosine, unpack_upper
from whyfinder.graph.build import GameInfo, Graph, Weights, build_graph, check_graph
from whyfinder.graph.ppr import pi_rows, push
from whyfinder.rerank.dpp import SparseVector, tfidf_vectors
from whyfinder.rerank.pipeline import recommend

MODEL_VERSION = 1

#: Histories the goldens cover, by title; titles missing from a slice are skipped.
GOLDEN_HISTORIES: tuple[tuple[tuple[str, float], ...], ...] = (
    (("Portal 2", 40.0), ("Half-Life 2", 25.0), ("Undertale", 12.0)),
    (("Rust", 300.0), ("DayZ", 120.0), ("Arma 3", 80.0)),
    (
        ("FTL: Faster Than Light", 60.0),
        ("The Binding of Isaac", 90.0),
        ("XCOM: Enemy Unknown", 45.0),
    ),
    (("Factorio", 150.0),),
    (
        ("DARK SOULS™ III", 120.0),
        ("The Witcher 2: Assassins of Kings Enhanced Edition", 40.0),
        ("Mount & Blade: Warband", 30.0),
        ("Starbound", 20.0),
        ("Stellaris", 0.0),
    ),
)


@dataclass(frozen=True)
class Model:
    params: dict[str, Any]
    games: list[dict[str, Any]]
    G: np.ndarray
    B: np.ndarray
    graph: Graph
    Pi: np.ndarray
    c_B: float
    c_Pi: float
    M: np.ndarray
    vectors: list[SparseVector]
    timings: dict[str, float]
    truncation_loss: np.ndarray

    @property
    def game_ids(self) -> list[int]:
        return [int(g["id"]) for g in self.games]


def model_params(p: dict[str, Any]) -> dict[str, Any]:
    """The subset of params.yaml both engines use, in the browser's naming."""
    g, w = p["graph"], p["graph"]["weights"]
    return {
        "lambda": float(p["ease"]["lambda"]),
        "restartAlpha": float(g["restart_alpha"]),
        "pushEps": float(g["push_eps"]),
        "topM": int(g["top_m"]),
        "tagsPerGame": int(g["tags_per_game"]),
        "coplayPerGame": int(g["coplay_per_game"]),
        "weights": {k: float(w[k]) for k in ("tag", "developer", "publisher", "coplay")},
        "beta": float(p["blend"]["beta"]),
        "topKPerRow": int(p["blend"]["top_k_per_row"]),
        "candidates": int(p["dpp"]["candidates"]),
        "theta": float(p["dpp"]["theta"]),
        "k": int(p["eval"]["k"]),
        "confidence": {k: float(v) for k, v in p["data"]["confidence"].items()},
    }


def dpp_features(games: Sequence[dict[str, Any]]) -> list[list[str]]:
    """Tags plus genres (prefixed so a tag and a genre with the same name stay distinct)."""
    return [list(g["tags"]) + [f"genre:{x}" for x in g["genres"]] for g in games]


def build_model(slice_: dict[str, Any], params: dict[str, Any]) -> Model:
    games = slice_["games"]
    n = int(slice_["gram"]["n"])
    G = unpack_upper(slice_["gram"]["packed_upper"], n).astype(np.float64)
    t0 = time.perf_counter()
    B = ease(G, params["lambda"])
    t1 = time.perf_counter()
    infos = [GameInfo(g["tags"], g["developer"], g["publisher"]) for g in games]
    graph = build_graph(
        infos,
        cosine(G),
        weights=Weights(**params["weights"]),
        tags_per_game=params["tagsPerGame"],
        coplay_per_game=params["coplayPerGame"],
    )
    check_graph(graph)
    t2 = time.perf_counter()
    Pi, loss = pi_rows(
        graph, alpha=params["restartAlpha"], eps=params["pushEps"], top_m=params["topM"]
    )
    t3 = time.perf_counter()
    c_B, c_Pi = scale_constant(B), scale_constant(Pi)
    M = blend(B, Pi, params["beta"], c_B, c_Pi)
    return Model(
        params=params,
        games=games,
        G=G,
        B=B,
        graph=graph,
        Pi=Pi,
        c_B=c_B,
        c_Pi=c_Pi,
        M=M,
        vectors=tfidf_vectors(dpp_features(games)),
        timings={"ease": t1 - t0, "graph": t2 - t1, "pi": t3 - t2},
        truncation_loss=loss,
    )


def model_file(model: Model) -> dict[str, Any]:
    return {
        "version": MODEL_VERSION,
        "params": model.params,
        "cB": model.c_B,
        "cPi": model.c_Pi,
        "build": {
            "easeSeconds": round(model.timings["ease"], 4),
            "piSeconds": round(model.timings["pi"], 4),
            "graphNodes": model.graph.n_nodes,
            "graphEdges": int(len(model.graph.indices) // 2),
            "piTruncationLoss": {
                "mean": round(float(model.truncation_loss.mean()), 6),
                "max": round(float(model.truncation_loss.max()), 6),
            },
        },
    }


def _sparse(row: np.ndarray) -> list[list[float]]:
    return [[int(i), float(row[i])] for i in np.flatnonzero(row)]


def goldens(model: Model) -> dict[str, Any]:
    """What the TypeScript engine must reproduce (see web/src/engine/engine.test.ts)."""
    p = model.params
    ids = model.game_ids
    by_title = {g["title"]: i for i, g in enumerate(model.games)}
    alpha, eps = p["confidence"]["alpha"], p["confidence"]["eps"]
    probe = [i for i in (0, model.graph.n_games // 2, model.graph.n_games - 1)]

    def run(history: list[tuple[int, float]]) -> list[int]:
        return recommend(
            history,
            model.M,
            vectors=model.vectors,
            game_ids=ids,
            k=p["k"],
            n_candidates=p["candidates"],
            theta=p["theta"],
        ).picks

    cases: list[dict[str, Any]] = []
    first_seed: int | None = None
    for spec in GOLDEN_HISTORIES:
        if any(title not in by_title for title, _ in spec):
            continue
        history = [
            (by_title[title], float(confidence(np.array([hours]), alpha, eps)[0]))
            for title, hours in spec
        ]
        if first_seed is None:
            first_seed = history[0][0]
        rec = recommend(
            history,
            model.M,
            vectors=model.vectors,
            game_ids=ids,
            k=p["k"],
            n_candidates=p["candidates"],
            theta=p["theta"],
        )
        picks = []
        for pick in rec.picks:
            parts = attributions(
                history,
                pick,
                model.M,
                model.B,
                model.Pi,
                beta=p["beta"],
                c_B=model.c_B,
                c_Pi=model.c_Pi,
                game_ids=ids,
            )
            cf = greedy(run, history, pick, [c.game for c in parts])
            paths = related_by(model.graph, parts[0].game, pick)
            picks.append(
                {
                    "pick": pick,
                    "score": float(rec.scores[pick]),
                    "attributions": [[c.game, c.total, c.ease, c.ppr] for c in parts],
                    "counterfactual": {"removed": cf.removed, "runs": cf.runs},
                    "paths": [[q.via, q.kind, q.weight] for q in paths],
                }
            )
        cases.append(
            {
                "titles": [title for title, _ in spec],
                "hours": [hours for _, hours in spec],
                "history": [[j, x] for j, x in history],
                "candidates": rec.candidates,
                "candidateScores": [float(rec.scores[i]) for i in rec.candidates],
                "relevanceTop": rec.relevance_top,
                "picks": picks,
                "variety": rec.variety,
                "dppGains": [s.gain for s in rec.steps],
            }
        )
    seeds = [first_seed if first_seed is not None else 0]
    push_results = [push(model.graph, s, alpha=p["restartAlpha"], eps=p["pushEps"]) for s in seeds]
    return {
        "version": MODEL_VERSION,
        "cB": model.c_B,
        "cPi": model.c_Pi,
        "graph": {
            "nodes": model.graph.n_nodes,
            "edges": int(len(model.graph.indices) // 2),
            "degree": [float(d) for d in model.graph.degree],
            "names": model.graph.names[model.graph.n_games :],
        },
        "bRows": {str(i): [float(v) for v in model.B[i]] for i in probe},
        "piRows": {str(i): _sparse(model.Pi[i]) for i in probe},
        "push": [
            {
                "seed": s,
                "rounds": r.rounds,
                "pushes": r.pushes,
                "residual": r.residual_mass,
                "p": _sparse(r.p),
            }
            for s, r in zip(seeds, push_results, strict=True)
        ],
        "cases": cases,
    }
