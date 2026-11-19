"""Fixed-budget tuning on the validation split (docs/spec/07_EVALUATION.md, "Protocol").

One grid per model, in params.yaml under `tune`, searched in this order so each step builds on the
last: EASE^R's λ, item-kNN's shrinkage, iALS's (reg, α), then the blend's β with the best λ, then
DPP's θ on the best blend. Every candidate is scored by mean NDCG@10 on the same users. θ is chosen
as the one with the highest ILD@10 whose NDCG@10 stays within `tune.dpp_ndcg_budget` of the blend
ranked by score alone (04_ALGORITHMS.md §A6). Ties go to the earlier grid value.
"""

from __future__ import annotations

import itertools
import time
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from whyfinder.core.baselines import gram, item_knn
from whyfinder.core.blend import blend, scale_constant, score, top_k_rows
from whyfinder.core.ease import ease
from whyfinder.core.ials import fold_in, ials
from whyfinder.eval import metrics
from whyfinder.eval.harness import EvalSet, History, game_infos, top_n
from whyfinder.graph.build import Weights, build_graph
from whyfinder.graph.ppr import pi_rows
from whyfinder.rerank.dpp import tfidf_vectors
from whyfinder.rerank.pipeline import recommend


def _ndcg(es: EvalSet, rank: Callable[[History], list[int]]) -> tuple[float, list[list[int]]]:
    ranked = [rank(es.history(k)) for k in range(len(es.users))]
    return float(metrics.ndcg_at(ranked, es.relevant, 10).mean()), ranked


def _best(rows: list[dict[str, Any]], key: str = "ndcg_at_10") -> dict[str, Any]:
    return max(rows, key=lambda r: (r[key], -rows.index(r)))


def tune(es: EvalSet, games: pd.DataFrame, p: dict[str, Any], *, seed: int) -> dict[str, Any]:
    """Search every grid; return every candidate's score and the chosen values."""
    grid = p["tune"]
    ids = es.game_ids
    t0 = time.perf_counter()
    G = gram(es.X)

    def item_item(W: np.ndarray) -> Callable[[History], list[int]]:
        return lambda h: top_n(score(h, W), {j for j, _ in h}, ids, 10)

    out: dict[str, Any] = {"users": len(es.users), "games": es.n_items, "grids": {}, "best": {}}

    rows: list[dict[str, Any]] = [
        {"lambda": float(lam), "ndcg_at_10": _ndcg(es, item_item(ease(G, float(lam))))[0]}
        for lam in grid["ease_lambda"]
    ]
    out["grids"]["ease"] = rows
    lam = _best(rows)["lambda"]
    out["best"]["ease.lambda"] = lam

    rows = []
    for s in grid["knn_shrinkage"]:
        S = item_knn(G, shrinkage=float(s), top_k=int(p["knn"]["top_k"]))
        rows.append({"shrinkage": float(s), "ndcg_at_10": _ndcg(es, item_item(S))[0]})
    out["grids"]["knn"] = rows
    out["best"]["knn.shrinkage"] = _best(rows)["shrinkage"]

    rows = []
    q = p["ials"]
    for reg, alpha in itertools.product(grid["ials_reg"], grid["ials_alpha"]):
        model = ials(
            es.X,
            factors=int(q["factors"]),
            reg=float(reg),
            alpha=float(alpha),
            sweeps=int(q["sweeps"]),
            seed=seed,
            solver=q.get("solver", "cg"),
            cg_steps=int(q.get("cg_steps", 3)),
            track_loss=False,
        )
        Y = model.item_factors

        def rank(
            h: History, Y: np.ndarray = Y, reg: float = float(reg), alpha: float = float(alpha)
        ) -> list[int]:
            return top_n(Y @ fold_in(h, Y, reg=reg, alpha=alpha), {j for j, _ in h}, ids, 10)

        rows.append({"reg": float(reg), "alpha": float(alpha), "ndcg_at_10": _ndcg(es, rank)[0]})
    out["grids"]["ials"] = rows
    best_ials = _best(rows)
    out["best"]["ials.reg"] = best_ials["reg"]
    out["best"]["ials.alpha"] = best_ials["alpha"]

    g = p["graph"]
    infos, features = game_infos(games, ids)
    d = np.sqrt(np.maximum(np.diag(G), 1.0))
    cos = G / np.outer(d, d)
    np.fill_diagonal(cos, 0.0)
    graph = build_graph(
        infos,
        cos,
        weights=Weights(**g["weights"]),
        tags_per_game=int(g["tags_per_game"]),
        coplay_per_game=int(g["coplay_per_game"]),
    )
    Pi, _ = pi_rows(
        graph, alpha=float(g["restart_alpha"]), eps=float(g["push_eps"]), top_m=int(g["top_m"])
    )
    B = ease(G, lam)
    c_B, c_Pi = scale_constant(B), scale_constant(Pi)
    rows = []
    blends: dict[float, np.ndarray] = {}
    for beta in grid["blend_beta"]:
        M = top_k_rows(blend(B, Pi, float(beta), c_B, c_Pi), int(p["blend"]["top_k_per_row"]))
        blends[float(beta)] = M
        rows.append({"beta": float(beta), "ndcg_at_10": _ndcg(es, item_item(M))[0]})
    out["grids"]["blend"] = rows
    best_blend = _best(rows)
    beta = best_blend["beta"]
    out["best"]["blend.beta"] = beta

    vectors = tfidf_vectors(features)
    M = blends[beta]
    id_list = ids.tolist()
    budget = float(grid["dpp_ndcg_budget"])
    rows = []
    for theta in grid["dpp_theta"]:

        def served(h: History, theta: float = float(theta)) -> list[int]:
            return recommend(
                h,
                M,
                vectors=vectors,
                game_ids=id_list,
                k=10,
                n_candidates=int(p["dpp"]["candidates"]),
                theta=theta,
            ).picks

        ndcg, ranked = _ndcg(es, served)
        rows.append(
            {
                "theta": float(theta),
                "ndcg_at_10": ndcg,
                "ild_at_10": float(metrics.ild(ranked, vectors, 10).mean()),
                "within_budget": ndcg >= best_blend["ndcg_at_10"] - budget,
            }
        )
    out["grids"]["dpp"] = rows
    allowed = [r for r in rows if r["within_budget"]] or [max(rows, key=lambda r: r["ndcg_at_10"])]
    out["best"]["dpp.theta"] = _best(allowed, key="ild_at_10")["theta"]
    out["seconds"] = round(time.perf_counter() - t0, 1)
    return out
