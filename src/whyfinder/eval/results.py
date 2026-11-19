"""Turn an evaluation report into the files under results/ that the README tables are built from.

One file per model: {"model", "split", "metrics": {name: {"mean", "lo", "hi"}}}, the means with a
95% bootstrap interval over users (scripts/gen_readme_tables.py reads exactly this shape), and
results/targets/<split>.json: every ADR-0006 target, met or not.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from whyfinder.eval.stats import Comparison, bootstrap_indices, holm, paired

REPORTED = ("ndcg_at_10", "recall_at_20", "mrr", "ild_at_10")
DIVERSITY = "DPP closes ≥ 10% of the ILD@10 headroom at an NDCG@10 cost ≤ 0.005"


def summarize(
    report: dict[str, Any], split: str, *, resamples: int, seed: int
) -> list[dict[str, Any]]:
    """Mean and 95% percentile interval of each reported metric, per model (shared resamples)."""
    n = len(report["users"])
    if n == 0:
        raise ValueError("the report has no users")
    idx = bootstrap_indices(n, resamples, seed)
    out = []
    for model, block in report["models"].items():
        metrics: dict[str, dict[str, float]] = {}
        for name in REPORTED:
            values = np.asarray(block["per_user"][name], dtype=np.float64)
            means = values[idx].mean(axis=1)
            lo, hi = np.quantile(means, [0.025, 0.975])
            metrics[name] = {
                "mean": round(float(values.mean()), 6),
                "lo": round(float(lo), 6),
                "hi": round(float(hi), 6),
            }
        metrics["coverage_at_10"] = {
            "mean": round(float(block["coverage_at_10"]), 6),
            "lo": round(float(block["coverage_at_10"]), 6),
            "hi": round(float(block["coverage_at_10"]), 6),
        }
        out.append({"model": model, "split": split, "users": n, "metrics": metrics})
    return out


def targets(
    report: dict[str, Any], *, resamples: int, seed: int, alpha: float = 0.05
) -> dict[str, Any]:
    """Each ADR-0006 target on one report: its value, the evidence, and whether it is met.

    Ranking and diversity use the paired bootstrap of `stats.paired` on the same users; the two
    superiority tests against popularity share a Holm–Bonferroni correction. A target whose models
    are missing from the report is listed with `met: None`.
    """
    models = report["models"]
    n = len(report["users"])
    if n == 0:
        raise ValueError("the report has no users")
    idx = bootstrap_indices(n, resamples, seed)

    def per_user(model: str, metric: str) -> np.ndarray | None:
        block = models.get(model)
        return None if block is None else np.asarray(block["per_user"][metric], dtype=np.float64)

    def compare(base: str, head: str, metric: str, margin: float) -> Comparison | None:
        b, h = per_user(base, metric), per_user(head, metric)
        if b is None or h is None:
            return None
        return paired(b, h, margin=margin, resamples=resamples, seed=seed, indices=idx)

    def show(c: Comparison) -> str:
        return (
            f"{c.head:.4f} vs {c.base:.4f}, Δ {c.delta:+.4f} "
            f"(95% CI {c.low:+.4f}, {c.high:+.4f}), p = {c.p_value:.3f}"
        )

    rows: list[dict[str, Any]] = []
    vs_ials = compare("ials", "blend", "ndcg_at_10", 0.005)
    rows.append(
        {
            "id": "ranking-ials",
            "target": "Blend non-inferior to iALS on NDCG@10 (δ = 0.005)",
            "detail": None if vs_ials is None else show(vs_ials),
            "met": None if vs_ials is None else vs_ials.p_value < alpha,
        }
    )
    vs_pop = [compare("popularity", "whyfinder", m, 0.0) for m in ("ndcg_at_10", "recall_at_20")]
    passed: list[bool | None] = [None, None]
    if all(c is not None for c in vs_pop):
        passed = list(holm([c.p_value for c in vs_pop if c is not None], alpha))
    for c, ok, label in zip(vs_pop, passed, ("NDCG@10", "Recall@20"), strict=True):
        rows.append(
            {
                "id": f"ranking-popularity-{label.lower().replace('@', '-at-')}",
                "target": f"Whyfinder beats popularity on {label} (p < 0.05, Holm over two)",
                "detail": None if c is None else show(c),
                "met": ok,
            }
        )
    ild_why, ild_blend = per_user("whyfinder", "ild_at_10"), per_user("blend", "ild_at_10")
    cost = compare("blend", "whyfinder", "ndcg_at_10", 0.005)
    if ild_why is None or ild_blend is None or cost is None:
        rows.append({"id": "diversity", "target": DIVERSITY, "detail": None, "met": None})
    else:
        headroom = 1.0 - float(ild_blend.mean())
        share = (float(ild_why.mean()) - float(ild_blend.mean())) / headroom if headroom else 0.0
        rows.append(
            {
                "id": "diversity",
                "target": DIVERSITY,
                "detail": (
                    f"ILD@10 {ild_blend.mean():.4f} → {ild_why.mean():.4f}, "
                    f"{share:.1%} of the headroom; NDCG@10 {show(cost)}"
                ),
                "met": share >= 0.10 and cost.p_value < alpha,
            }
        )
    explain = report.get("explanations", {}).get("means", {})
    for key, target, bar in (
        ("additivity", "Attributions sum to the score (share of picks)", 1.0),
        ("cf_validity", "Counterfactuals valid (share of picks)", 1.0),
        ("deletion", "Deletion test ≥ 95% of users", 0.95),
    ):
        value = explain.get(key)
        rows.append(
            {
                "id": key.replace("_", "-"),
                "target": target,
                "detail": None if value is None else f"{value:.4f}",
                "met": None if value is None else value >= bar,
            }
        )
    return {"split": report.get("split", "test"), "users": n, "targets": rows}
