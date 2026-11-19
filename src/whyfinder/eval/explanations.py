"""Explanation checks (05_EXPLAINABILITY.md, "How explanations are measured"; FR-10, FR-11).

Run on the served pipeline (blend + DPP) for each of the first `users` evaluation users, about their
first pick:

- **Additivity:** 1 if the contributions sum to the pipeline's score within 1e-9. Gate: every user.
- **Deletion:** 1 if removing the 3 most-attributed games pushes the pick further down the ranking
  than removing 3 random games of the same user (mean rank over `draws` draws). Gate: non-inferior.
- **Counterfactual validity:** 1 if removing the greedy set drops the pick from the re-run
  pipeline. Gate: every user.
- **Minimality gap:** greedy size − exact size (exact over the `pool` largest contributors, size
  ≤ 3). Lower is better. Gate: non-inferior.
- **Sanity check:** Spearman correlation between the pick's contributions under M and under M with
  its rows shuffled (Adebayo et al., NeurIPS 2018); near 0 means the attributions depend on the
  model. Reported.

Values that do not apply to a user are NaN: the deletion test needs at least 4 games, the gap needs
an exact set within the pool, the sanity check needs 3 games.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from whyfinder.eval.harness import EvalSet, History, Served
from whyfinder.explain.attributions import attributions
from whyfinder.explain.counterfactual import exact, greedy
from whyfinder.rerank.pipeline import recommend

CHECKS = ("additivity", "deletion", "cf_validity", "minimality_gap", "sanity_spearman")


def _rank_after(
    scores: np.ndarray, history: History, removed: set[int], pick: int, ids: np.ndarray
) -> int:
    """1-based rank of `pick` by score once `removed` leave the history (scores already updated)."""
    owned = np.zeros(scores.size, dtype=bool)
    for j, _ in history:
        if j not in removed:
            owned[j] = True
    s = scores[pick]
    better = (scores > s) | ((scores == s) & (ids < ids[pick]))
    return 1 + int(np.sum(better & ~owned))


def _rank_without(
    served: Served,
    scores: np.ndarray,
    weight: dict[int, float],
    history: History,
    removed: set[int],
    pick: int,
    ids: np.ndarray,
) -> int:
    """Rank of `pick` after removing games: scores are linear, so subtract their rows."""
    updated = scores.copy()
    for j in sorted(removed):
        updated = updated - weight[j] * served.M[j]
    return _rank_after(updated, history, removed, pick, ids)


def _ranks(a: np.ndarray) -> np.ndarray:
    """Ranks with ties sharing their average rank."""
    order = np.argsort(a, kind="stable")
    ranks = np.empty(a.size, dtype=np.float64)
    values = a[order]
    start = 0
    while start < a.size:
        stop = start
        while stop + 1 < a.size and values[stop + 1] == values[start]:
            stop += 1
        ranks[order[start : stop + 1]] = (start + stop) / 2.0
        start = stop + 1
    return ranks


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman's rank correlation (0 when either side is constant)."""
    ra, rb = _ranks(a), _ranks(b)
    if np.std(ra) == 0 or np.std(rb) == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def check(
    es: EvalSet, served: Served, *, users: int, pool: int, draws: int, seed: int
) -> dict[str, Any]:
    """Per-user explanation checks for the first `users` evaluation users (JSON-ready)."""
    if users < 1 or pool < 1 or draws < 1:
        raise ValueError("users, pool and draws must be positive")
    rng = np.random.default_rng(seed)
    n_users = min(users, len(es.users))
    perm = rng.permutation(served.M.shape[0])
    out: dict[str, list[float]] = {name: [] for name in CHECKS}
    runs: list[int] = []
    ids = served.game_ids
    id_array = np.asarray(ids, dtype=np.int64)
    for k in range(n_users):
        history = es.history(k)
        rec = recommend(
            history,
            served.M,
            vectors=served.vectors,
            game_ids=ids,
            k=10,
            n_candidates=served.candidates,
            theta=served.theta,
        )
        picks = rec.picks
        if not picks:
            for name in CHECKS:
                out[name].append(float("nan"))
            runs.append(0)
            continue
        pick = picks[0]
        contributions = attributions(
            history,
            pick,
            served.M,
            served.B,
            served.Pi,
            beta=served.beta,
            c_B=served.c_B,
            c_Pi=served.c_Pi,
            game_ids=ids,
        )
        scores = rec.scores
        total = sum(c.total for c in contributions)
        out["additivity"].append(float(abs(total - scores[pick]) <= 1e-9))

        order = [c.game for c in contributions]
        weight = dict(history)
        if len(history) >= 4:
            attributed = _rank_without(
                served, scores, weight, history, set(order[:3]), pick, id_array
            )
            games = [j for j, _ in history]
            random_ranks = [
                _rank_without(
                    served,
                    scores,
                    weight,
                    history,
                    set(rng.choice(games, size=3, replace=False).tolist()),
                    pick,
                    id_array,
                )
                for _ in range(draws)
            ]
            out["deletion"].append(float(attributed > float(np.mean(random_ranks))))
        else:
            out["deletion"].append(float("nan"))

        cf = greedy(served.run, history, pick, order)
        rest = [(j, x) for j, x in history if j not in set(cf.removed)]
        out["cf_validity"].append(float(not rest or pick not in served.run(rest)))
        best = exact(served.run, history, pick, order, max_size=3, pool=pool)
        out["minimality_gap"].append(
            float(len(cf.removed) - len(best.removed)) if best is not None else float("nan")
        )
        runs.append(cf.runs + (best.runs if best is not None else 0))

        if len(history) >= 3:
            real = np.array([x * served.M[j, pick] for j, x in history])
            shuffled = np.array([x * served.M[perm[j], pick] for j, x in history])
            out["sanity_spearman"].append(_spearman(real, shuffled))
        else:
            out["sanity_spearman"].append(float("nan"))

    def mean(values: list[float]) -> float | None:
        finite = [v for v in values if not np.isnan(v)]
        return float(np.mean(finite)) if finite else None

    return {
        "users": n_users,
        "pool": pool,
        "draws": draws,
        "pipeline_runs_mean": float(np.mean(runs)) if runs else 0.0,
        "means": {name: mean(values) for name, values in out.items()},
        "per_user": {
            name: [None if np.isnan(v) else round(v, 6) for v in values]
            for name, values in out.items()
        },
    }
