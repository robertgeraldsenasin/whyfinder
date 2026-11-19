"""Turn an evaluation report into the files under results/ that the README table is built from.

One file per model: {"model", "split", "metrics": {name: {"mean", "lo", "hi"}}}, the means with a
95% bootstrap interval over users (scripts/gen_readme_tables.py reads exactly this shape).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from whyfinder.eval.stats import bootstrap_indices

REPORTED = ("ndcg_at_10", "recall_at_20", "mrr", "ild_at_10")


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
