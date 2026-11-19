"""The quality gate (FR-20): compare a pull request's evaluation with main's, user by user.

Both reports come from `whyfinder eval` on the same users. For the served model (`whyfinder`), each
gated metric must be non-inferior to main within its margin (superiority when the PR carries the
`model:gainer` label), with Holm–Bonferroni across the gated metrics. Coverage and popularity are
reported, not gated. The Markdown follows docs/spec/07_EVALUATION.md, "PR comment format".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from whyfinder.eval.stats import Comparison, bootstrap_indices, holm, paired

MARKER = "<!-- whyfinder-gate -->"
SERVED = "whyfinder"
#: Explanation checks: how each is gated (05_EXPLAINABILITY.md).
EXPLAIN_LABELS = {
    "additivity": "Additivity (share of picks)",
    "cf_validity": "Counterfactual validity",
    "deletion": "Deletion test (share of users)",
    "minimality_gap": "Minimality gap (greedy − exact)",
    "sanity_spearman": "Shuffled-model rank correlation",
}
MUST_BE_ONE = ("additivity", "cf_validity")
LOWER_IS_BETTER = ("minimality_gap",)
LABELS = {
    "ndcg_at_10": "NDCG@10",
    "recall_at_20": "Recall@20",
    "mrr": "MRR",
    "ild_at_10": "ILD@10",
    "arp_at_10": "ARP@10 (share of top popularity)",
}


class GateError(ValueError):
    """The two reports cannot be compared."""


@dataclass(frozen=True)
class Verdict:
    passed: bool
    rows: list[tuple[str, Comparison, bool | None]]
    markdown: str


def _per_user(report: dict[str, Any], model: str) -> dict[str, np.ndarray]:
    try:
        block = report["models"][model]["per_user"]
    except KeyError as error:
        raise GateError(f"report has no per-user metrics for model {model!r}") from error
    return {m: np.asarray(v, dtype=np.float64) for m, v in block.items()}


def _explain_arrays(report: dict[str, Any]) -> dict[str, np.ndarray]:
    block = report.get("explanations", {}).get("per_user", {})
    return {
        m: np.array([np.nan if x is None else x for x in v], dtype=np.float64)
        for m, v in block.items()
    }


def _explain_rows(
    base: dict[str, Any],
    head: dict[str, Any],
    margins: dict[str, float],
    resamples: int,
    seed: int,
) -> list[tuple[str, Comparison, str]]:
    """Paired comparisons of the explanation checks on users where both runs have a value."""
    b, h = _explain_arrays(base), _explain_arrays(head)
    rows: list[tuple[str, Comparison, str]] = []
    for metric in ("deletion", "minimality_gap", "sanity_spearman"):
        if metric not in b or metric not in h or b[metric].shape != h[metric].shape:
            continue
        both = ~np.isnan(b[metric]) & ~np.isnan(h[metric])
        if not both.any():
            continue
        sign = -1.0 if metric in LOWER_IS_BETTER else 1.0
        c = paired(
            sign * b[metric][both],
            sign * h[metric][both],
            margin=margins.get(metric, 0.0),
            resamples=resamples,
            seed=seed,
        )
        if sign < 0:
            c = Comparison(-c.base, -c.head, -c.delta, -c.high, -c.low, c.p_value, c.margin, c.n)
        rows.append((metric, c, "gated" if metric in margins else "report"))
    return rows


def compare(
    base: dict[str, Any] | None,
    head: dict[str, Any],
    *,
    margins: dict[str, float],
    resamples: int,
    seed: int,
    superiority: bool = False,
    alpha: float = 0.05,
    explain_margins: dict[str, float] | None = None,
) -> Verdict:
    """Gate head against base. With no base (main has no evaluation yet) the gate passes."""
    head_models = head.get("models", {})
    lines = [MARKER]
    head_explain = head.get("explanations", {}).get("means", {})
    exact_failures = [
        m
        for m in MUST_BE_ONE
        if m in head_explain and head_explain[m] is not None and head_explain[m] < 1.0
    ]
    if base is None:
        lines.append("### Whyfinder quality gate: PASS (no baseline on main yet)")
        lines.append("")
        lines.append(
            "Main has no `whyfinder eval` yet, so this run becomes the baseline. "
            "Validation means on the CI subsample:"
        )
        lines.append("")
        lines += _summary_table(head_models)
        lines += _explain_summary(head)
        lines.append("")
        lines.append(_footer(head, resamples, seed))
        if exact_failures:
            lines[1] = "### Whyfinder quality gate: FAIL (explanations)"
        return Verdict(not exact_failures, [], "\n".join(lines) + "\n")
    if base.get("users") != head.get("users"):
        raise GateError("base and head were evaluated on different users")
    b, h = _per_user(base, SERVED), _per_user(head, SERVED)
    n = len(head["users"])
    idx = bootstrap_indices(n, resamples, seed)
    rows: list[tuple[str, Comparison, bool | None]] = []
    gated: list[tuple[str, Comparison]] = []
    for metric in LABELS:
        if metric not in b or metric not in h:
            continue
        is_gated = metric in margins
        margin = 0.0 if superiority else margins.get(metric, 0.0)
        c = paired(b[metric], h[metric], margin=margin, resamples=resamples, seed=seed, indices=idx)
        rows.append((metric, c, None))
        if is_gated:
            gated.append((metric, c))
    explain_rows = _explain_rows(base, head, explain_margins or {}, resamples, seed)
    for metric, c, kind in explain_rows:
        if kind == "gated":
            gated.append((f"explain:{metric}", c))
    passes = holm([c.p_value for _, c in gated], alpha=alpha)
    verdicts = dict(zip([m for m, _ in gated], passes, strict=True))
    rows = [(m, c, verdicts.get(m)) for m, c, _ in rows]
    passed = (all(passes) if passes else True) and not exact_failures
    kind = "superior" if superiority else "non-inferior"
    lines.append(f"### Whyfinder quality gate: {'PASS' if passed else 'FAIL'}")
    lines.append("")
    lines.append("| Metric | main | this PR | Δ (95% CI) | Gate |")
    lines.append("| --- | --- | --- | --- | --- |")
    for metric, c, ok in rows:
        gate = (
            "report only"
            if ok is None
            else (f"{kind} ✓" if ok else f"{kind} ✗ (p = {c.p_value:.3f})")
        )
        lines.append(
            f"| {LABELS[metric]} | {c.base:.4f} | {c.head:.4f} "
            f"| {c.delta:+.4f} ({c.low:+.4f}, {c.high:+.4f}) | {gate} |"
        )
    cov_b = base["models"][SERVED]["coverage_at_10"]
    cov_h = head["models"][SERVED]["coverage_at_10"]
    lines.append(
        f"| Coverage@10 | {cov_b:.4f} | {cov_h:.4f} | {cov_h - cov_b:+.4f} | report only |"
    )
    base_explain = base.get("explanations", {}).get("means", {})
    for metric in MUST_BE_ONE:
        value = head_explain.get(metric)
        if value is None:
            continue
        before = base_explain.get(metric)
        shown = "" if before is None else f"{before:.4f}"
        lines.append(
            f"| {EXPLAIN_LABELS[metric]} | {shown} | {value:.4f} | "
            f"| {'100% ✓' if value >= 1.0 else '100% ✗'} |"
        )
    for metric, c, kind in explain_rows:
        ok = verdicts.get(f"explain:{metric}") if kind == "gated" else None
        word = "superior" if superiority else "non-inferior"
        gate = (
            "report only"
            if ok is None
            else (f"{word} ✓" if ok else f"{word} ✗ (p = {c.p_value:.3f})")
        )
        lines.append(
            f"| {EXPLAIN_LABELS[metric]} | {c.base:.4f} | {c.head:.4f} "
            f"| {c.delta:+.4f} ({c.low:+.4f}, {c.high:+.4f}) | {gate} |"
        )
    lines.append("")
    lines.append(
        "Margins: "
        + ", ".join(f"{LABELS[m]} δ = {margins[m]}" for m in margins if m in LABELS)
        + f"; Holm–Bonferroni over {len(gated)} gated metrics at α = {alpha}."
    )
    lines.append("")
    lines.append("<details><summary>Every model on this PR</summary>")
    lines.append("")
    lines += _summary_table(head_models)
    lines += _explain_summary(head)
    lines.append("")
    lines.append("</details>")
    lines.append("")
    lines.append(_footer(head, resamples, seed))
    return Verdict(passed, rows, "\n".join(lines) + "\n")


def _explain_summary(report: dict[str, Any]) -> list[str]:
    block = report.get("explanations")
    if not block:
        return []
    out = ["", f"Explanation checks on the first {block['users']} users' first pick:", ""]
    out += ["| Check | Value |", "| --- | --- |"]
    for metric, value in block["means"].items():
        shown = "n/a" if value is None else f"{value:.4f}"
        out.append(f"| {EXPLAIN_LABELS.get(metric, metric)} | {shown} |")
    return out


def _summary_table(models: dict[str, Any]) -> list[str]:
    out = [
        "| Model | NDCG@10 | Recall@20 | MRR | ILD@10 | Coverage@10 | Build (s) | Peak (MB) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, block in models.items():
        m = block["means"]
        peak = block.get("info", {}).get("peak_mb")
        out.append(
            f"| {name} | {m['ndcg_at_10']:.4f} | {m['recall_at_20']:.4f} | {m['mrr']:.4f} "
            f"| {m['ild_at_10']:.4f} "
            f"| {block['coverage_at_10']:.4f} | {block['build_seconds']:.1f} "
            f"| {'' if peak is None else f'{peak:.0f}'} |"
        )
    return out


def _footer(report: dict[str, Any], resamples: int, seed: int) -> str:
    return (
        f"Sample: {report.get('sample', 'validation users')} (n = {len(report.get('users', []))}), "
        f"{report.get('n_items', '?')} games, seed {seed}, {resamples:,} resamples."
    )
