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


def compare(
    base: dict[str, Any] | None,
    head: dict[str, Any],
    *,
    margins: dict[str, float],
    resamples: int,
    seed: int,
    superiority: bool = False,
    alpha: float = 0.05,
) -> Verdict:
    """Gate head against base. With no base (main has no evaluation yet) the gate passes."""
    head_models = head.get("models", {})
    lines = [MARKER]
    if base is None:
        lines.append("### Whyfinder quality gate: PASS (no baseline on main yet)")
        lines.append("")
        lines.append(
            "Main has no `whyfinder eval` yet, so this run becomes the baseline. "
            "Validation means on the CI subsample:"
        )
        lines.append("")
        lines += _summary_table(head_models)
        lines.append("")
        lines.append(_footer(head, resamples, seed))
        return Verdict(True, [], "\n".join(lines) + "\n")
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
    passes = holm([c.p_value for _, c in gated], alpha=alpha)
    verdicts = dict(zip([m for m, _ in gated], passes, strict=True))
    rows = [(m, c, verdicts.get(m)) for m, c, _ in rows]
    passed = all(passes) if passes else True
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
    lines.append("")
    lines.append("</details>")
    lines.append("")
    lines.append(_footer(head, resamples, seed))
    return Verdict(passed, rows, "\n".join(lines) + "\n")


def _summary_table(models: dict[str, Any]) -> list[str]:
    out = [
        "| Model | NDCG@10 | Recall@20 | MRR | ILD@10 | Coverage@10 | Build (s) |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, block in models.items():
        m = block["means"]
        out.append(
            f"| {name} | {m['ndcg_at_10']:.4f} | {m['recall_at_20']:.4f} | {m['mrr']:.4f} "
            f"| {m['ild_at_10']:.4f} "
            f"| {block['coverage_at_10']:.4f} | {block['build_seconds']:.1f} |"
        )
    return out


def _footer(report: dict[str, Any], resamples: int, seed: int) -> str:
    return (
        f"Sample: {report.get('sample', 'validation users')} (n = {len(report.get('users', []))}), "
        f"{report.get('n_items', '?')} games, seed {seed}, {resamples:,} resamples."
    )
