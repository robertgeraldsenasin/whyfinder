"""Offline evaluation: build every model on train, rank for held-out users, score per user (FR-19).

The protocol follows docs/spec/07_EVALUATION.md: a user's history is their train games (inside the
item cap) with confidence weights; a model scores every game; owned games are removed and ties
break by game ID; the held-out games of the split are the relevant ones. Every model sees the same
users in the same order, so any two runs can be compared user by user.

Models:

| Name | What it is |
| --- | --- |
| popularity | summed train confidence (A1) |
| itemknn | cosine with shrinkage, top 100 per game (A1) |
| ease | EASE^R (A2) |
| ppr | Personalized PageRank over the game graph, Π alone (A4) |
| blend | the glass-box blend M, ranked by score (A5) |
| whyfinder | what the demo serves: the blend's top 100, DPP for the first 10, then by score (A6) |
| ials | the latent-factor rival, folded in per user (A3) |
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import scipy.sparse as sp

from whyfinder.core.baselines import gram, item_knn, popularity
from whyfinder.core.blend import blend, scale_constant, score, top_k_rows
from whyfinder.core.ease import ease
from whyfinder.core.ials import fold_in, ials
from whyfinder.data.features import build_features
from whyfinder.eval import metrics
from whyfinder.graph.build import GameInfo, Weights, build_graph, check_graph
from whyfinder.graph.ppr import pi_rows
from whyfinder.rerank.dpp import SparseVector, tfidf_vectors
from whyfinder.rerank.pipeline import recommend

History = list[tuple[int, float]]
Ranker = Callable[[History], list[int]]
MODELS = ("popularity", "itemknn", "ease", "ppr", "blend", "whyfinder", "ials")
#: Gated metrics and the metric each margin in params.yaml (eval.margins) applies to.
GATED = ("ndcg_at_10", "recall_at_20", "ild_at_10")


@dataclass(frozen=True)
class EvalSet:
    """Train matrix, catalogue columns and the held-out users, in a fixed order."""

    X: sp.csr_matrix
    game_ids: np.ndarray
    users: list[str]
    rows: np.ndarray
    relevant: list[set[int]]

    @property
    def n_items(self) -> int:
        return int(self.X.shape[1])

    def history(self, k: int) -> History:
        row = int(self.rows[k])
        start, stop = self.X.indptr[row], self.X.indptr[row + 1]
        cols = self.X.indices[start:stop].tolist()
        vals = self.X.data[start:stop].tolist()
        return list(zip(cols, vals, strict=True))


def eval_set(
    train: pd.DataFrame,
    holdout: pd.DataFrame,
    *,
    item_cap: int,
    alpha: float,
    eps: float,
    max_users: int | None = None,
) -> EvalSet:
    """Users of `holdout` with a train history inside the item cap and ≥ 1 held-out game inside it.

    Users are taken in ascending ID order (IDs are salted hashes, so this is an unbiased sample);
    `max_users` keeps the first that many.
    """
    features = build_features(train, item_cap=item_cap, alpha=alpha, eps=eps)
    col_of = pd.Series(features.items["col"].to_numpy(), index=features.items["game"].to_numpy())
    row_of = pd.Series(features.users["row"].to_numpy(), index=features.users["user"].to_numpy())
    kept = holdout.loc[holdout["game"].isin(col_of.index) & holdout["user"].isin(row_of.index)]
    grouped = kept.groupby("user", sort=True)["game"].apply(lambda g: sorted(set(g.tolist())))
    users = grouped.index.tolist()
    if max_users is not None:
        users = users[:max_users]
    relevant = [{int(col_of[g]) for g in grouped[u]} for u in users]
    rows = row_of.loc[users].to_numpy(dtype=np.int64) if users else np.zeros(0, dtype=np.int64)
    return EvalSet(
        X=features.X,
        game_ids=features.items["game"].to_numpy(dtype=np.int64),
        users=[str(u) for u in users],
        rows=rows,
        relevant=relevant,
    )


def top_n(scores: np.ndarray, owned: set[int], game_ids: np.ndarray, n: int) -> list[int]:
    """The n best columns by score, owned ones removed, ties by game ID."""
    keep = np.ones(scores.size, dtype=bool)
    if owned:
        keep[list(owned)] = False
    candidates = np.flatnonzero(keep)
    if candidates.size == 0:
        return []
    take = min(n + 64, candidates.size)
    part = candidates[np.argpartition(-scores[candidates], take - 1)[:take]]
    threshold = float(np.min(scores[part]))
    tied = candidates[scores[candidates] >= threshold]
    order = np.lexsort((game_ids[tied], -scores[tied]))
    return [int(i) for i in tied[order][:n]]


@dataclass
class Built:
    """A ranker plus how long the model took to build."""

    rank: Ranker
    seconds: float
    info: dict[str, Any] = field(default_factory=dict)


def _game_infos(
    games: pd.DataFrame, game_ids: np.ndarray
) -> tuple[list[GameInfo], list[list[str]]]:
    meta = games.drop_duplicates("game").set_index("game").reindex(game_ids)

    def text(value: object) -> str | None:
        return str(value) if isinstance(value, str) and value else None

    def items(value: object) -> list[str]:
        return [str(v) for v in value] if isinstance(value, list | tuple | np.ndarray) else []

    infos, features = [], []
    for _, row in meta.iterrows():
        tags, genres = items(row.get("tags")), items(row.get("genres"))
        infos.append(GameInfo(tags, text(row.get("developer")), text(row.get("publisher"))))
        features.append(tags + [f"genre:{g}" for g in genres])
    return infos, features


def build_models(
    es: EvalSet, games: pd.DataFrame, p: dict[str, Any], *, seed: int, only: Sequence[str] = MODELS
) -> tuple[dict[str, Built], list[SparseVector]]:
    """Build the requested models on es.X; returns rankers (top 20) and the DPP tag vectors."""
    unknown = sorted(set(only) - set(MODELS))
    if unknown:
        raise ValueError(f"unknown model(s): {', '.join(unknown)}")
    k_list = 20
    ids = es.game_ids
    built: dict[str, Built] = {}
    infos, features = _game_infos(games, ids)
    vectors = tfidf_vectors(features)

    def item_item(W: np.ndarray) -> Ranker:
        return lambda h: top_n(score(h, W), {j for j, _ in h}, ids, k_list)

    t = time.perf_counter()
    G = gram(es.X)
    t_gram = time.perf_counter() - t

    if "popularity" in only:
        t = time.perf_counter()
        pop = popularity(es.X)
        built["popularity"] = Built(
            lambda h: top_n(pop, {j for j, _ in h}, ids, k_list), time.perf_counter() - t
        )
    if "itemknn" in only:
        t = time.perf_counter()
        S = item_knn(G, shrinkage=float(p["knn"]["shrinkage"]), top_k=int(p["knn"]["top_k"]))
        built["itemknn"] = Built(item_item(S), t_gram + time.perf_counter() - t)
    need_b = bool({"ease", "blend", "whyfinder"} & set(only))
    need_pi = bool({"ppr", "blend", "whyfinder"} & set(only))
    B: np.ndarray | None = None
    Pi: np.ndarray | None = None
    if need_b:
        t = time.perf_counter()
        B = ease(G, float(p["ease"]["lambda"]))
        built_b = t_gram + time.perf_counter() - t
        if "ease" in only:
            built["ease"] = Built(item_item(B), built_b)
    if need_pi:
        t = time.perf_counter()
        g = p["graph"]
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
        check_graph(graph)
        Pi, losses = pi_rows(
            graph, alpha=float(g["restart_alpha"]), eps=float(g["push_eps"]), top_m=int(g["top_m"])
        )
        built_pi = t_gram + time.perf_counter() - t
        if "ppr" in only:
            built["ppr"] = Built(
                item_item(Pi), built_pi, {"truncation_loss_mean": float(np.mean(losses))}
            )
    if B is not None and Pi is not None:
        t = time.perf_counter()
        c_B, c_Pi = scale_constant(B), scale_constant(Pi)
        M = top_k_rows(
            blend(B, Pi, float(p["blend"]["beta"]), c_B, c_Pi), int(p["blend"]["top_k_per_row"])
        )
        seconds = time.perf_counter() - t
        info = {"c_B": c_B, "c_Pi": c_Pi, "beta": float(p["blend"]["beta"])}
        if "blend" in only:
            built["blend"] = Built(item_item(M), seconds, info)
        if "whyfinder" in only:
            dpp = p["dpp"]
            id_list = ids.tolist()

            def served(h: History, M: np.ndarray = M) -> list[int]:
                rec = recommend(
                    h,
                    M,
                    vectors=vectors,
                    game_ids=id_list,
                    k=10,
                    n_candidates=int(dpp["candidates"]),
                    theta=float(dpp["theta"]),
                )
                picked = set(rec.picks)
                rest = [i for i in rec.candidates if i not in picked]
                return rec.picks + rest[: k_list - len(rec.picks)]

            built["whyfinder"] = Built(served, seconds, info)
    if "ials" in only:
        q = p["ials"]
        t = time.perf_counter()
        model = ials(
            es.X,
            factors=int(q["factors"]),
            reg=float(q["reg"]),
            alpha=float(q["alpha"]),
            sweeps=int(q["sweeps"]),
            seed=seed,
            solver=q.get("solver", "cg"),
            cg_steps=int(q.get("cg_steps", 3)),
        )
        Y = model.item_factors
        reg, alpha = float(q["reg"]), float(q["alpha"])
        built["ials"] = Built(
            lambda h: top_n(
                Y @ fold_in(h, Y, reg=reg, alpha=alpha), {j for j, _ in h}, ids, k_list
            ),
            time.perf_counter() - t,
            {"losses": model.losses},
        )
    return built, vectors


def score_lists(
    ranked: list[list[int]], es: EvalSet, vectors: list[SparseVector], pop: np.ndarray
) -> dict[str, np.ndarray]:
    """Per-user metrics for one model's lists (aligned with es.users)."""
    return {
        "ndcg_at_10": metrics.ndcg_at(ranked, es.relevant, 10),
        "recall_at_20": metrics.recall_at(ranked, es.relevant, 20),
        "mrr": metrics.mrr(ranked, es.relevant),
        "ild_at_10": metrics.ild(ranked, vectors, 10),
        "arp_at_10": metrics.arp(ranked, pop, 10),
    }


def evaluate(
    es: EvalSet, games: pd.DataFrame, p: dict[str, Any], *, seed: int, only: Sequence[str] = MODELS
) -> dict[str, Any]:
    """Build, rank and score every requested model. JSON-ready, per-user arrays included."""
    built, vectors = build_models(es, games, p, seed=seed, only=only)
    pop = popularity(es.X)
    share = pop / pop.max() if pop.size and pop.max() > 0 else pop
    report: dict[str, Any] = {"users": es.users, "n_items": es.n_items, "models": {}}
    for name in MODELS:
        if name not in built:
            continue
        b = built[name]
        t = time.perf_counter()
        ranked = [b.rank(es.history(k)) for k in range(len(es.users))]
        rank_seconds = time.perf_counter() - t
        per_user = score_lists(ranked, es, vectors, share)
        report["models"][name] = {
            "build_seconds": round(b.seconds, 3),
            "rank_ms_per_user": round(1000 * rank_seconds / max(1, len(es.users)), 4),
            "info": b.info,
            "coverage_at_10": metrics.coverage(ranked, es.n_items, 10),
            "means": {m: float(v.mean()) if v.size else 0.0 for m, v in per_user.items()},
            "per_user": {m: [round(float(x), 6) for x in v] for m, v in per_user.items()},
        }
    return report
