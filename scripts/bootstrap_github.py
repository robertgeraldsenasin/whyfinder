"""Create labels, milestones and issues for Whyfinder from docs/plan/BACKLOG.csv.

Uses only the GitHub REST API through the `gh` CLI, so it works anywhere `gh` is logged in.
Idempotent: existing labels, milestones and issues (matched by title) are left alone.

Usage:
    python scripts/bootstrap_github.py --repo robertgeraldsenasin/whyfinder [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

LABELS = {
    "type:feat": ("1f6feb", "New capability"),
    "type:fix": ("d73a4a", "Bug fix"),
    "type:docs": ("0e8a16", "Documentation or ADR"),
    "type:chore": ("c5def5", "Tooling, infra, housekeeping"),
    "area:data": ("fbca04", "Data pipeline"),
    "area:core": ("f4b860", "Core models"),
    "area:graph": ("7dd3e3", "Game graph and PPR"),
    "area:rerank": ("8b7cf0", "DPP and filters"),
    "area:explain": ("6fd8a3", "Attributions, counterfactuals, paths"),
    "area:rag": ("bfd4f2", "Retrieval and grounded generation"),
    "area:eval": ("d4c5f9", "Metrics and gates"),
    "area:serve": ("5319e7", "API"),
    "area:web": ("e99695", "Star-atlas demo"),
    "area:infra": ("ededed", "CI/CD and repo"),
    "model:gainer": ("0e8a16", "Gate in superiority mode"),
    "gate:override": ("b60205", "Gate overridden; reason required in the PR"),
}
MILESTONES = {
    "M0": ("M0 Foundation", "2026-11-22", "Repo, CI, data pipeline, contracts, CI subsample"),
    "M1": ("M1 Glass-box core + gate", "2026-12-12", "Baselines, EASE^R, PPR, blend, iALS, gate"),
    "M2": ("M2 Explanations + variety", "2026-12-30", "Attributions, counterfactuals, DPP, paths"),
    "M3": ("M3 Grounded RAG", "2027-01-13", "BM25, HNSW, RRF, checked generation"),
    "M4": ("M4 Star-atlas demo, API, v1.0", "2027-01-24", "FastAPI, Docker, demo, release"),
}


def gh(args: list[str], payload: dict | None = None, dry: bool = False) -> object:
    if dry and payload is not None:
        print("DRY", " ".join(args), json.dumps(payload)[:120])
        return {}
    cmd = ["gh", "api", *args]
    if payload is not None:
        cmd += ["--input", "-"]
    out = subprocess.run(
        cmd,
        input=json.dumps(payload) if payload else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(f"gh api {' '.join(args)} failed: {out.stderr.strip()}")
    return json.loads(out.stdout) if out.stdout.strip() else {}


def paged(path: str) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        batch = gh([f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}"])
        if not isinstance(batch, list) or not batch:
            return items
        items += batch
        page += 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    base = f"repos/{a.repo}"

    have_labels = {label["name"] for label in paged(f"{base}/labels")}
    for name, (color, desc) in LABELS.items():
        if name not in have_labels:
            gh(
                [f"{base}/labels", "--method", "POST"],
                {"name": name, "color": color, "description": desc},
                a.dry_run,
            )
            print("label +", name)

    have_ms = {m["title"]: m["number"] for m in paged(f"{base}/milestones?state=all")}
    ms_number: dict[str, int] = {}
    for key, (title, due, desc) in MILESTONES.items():
        if title not in have_ms:
            res = gh(
                [f"{base}/milestones", "--method", "POST"],
                {"title": title, "due_on": f"{due}T23:59:59Z", "description": desc},
                a.dry_run,
            )
            have_ms[title] = res.get("number", 0) if isinstance(res, dict) else 0
            print("milestone +", title)
        ms_number[key] = have_ms[title]

    have_issues = {i["title"] for i in paged(f"{base}/issues?state=all") if "pull_request" not in i}
    backlog = Path(__file__).resolve().parents[1] / "docs" / "plan" / "BACKLOG.csv"
    with backlog.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["title"] in have_issues:
                continue
            reqs = ", ".join(r for r in row["requirements"].split(";") if r) or "—"
            body = (
                f"**Requirements:** {reqs}\n\n**Estimate:** {row['estimate_days']} day(s)\n\n"
                f"**Acceptance criterion**\n\n- [ ] {row['acceptance']}\n\n"
                "**Definition of done:** acceptance passes in CI; tests include a failure path; "
                "`make verify` passes; docs/ADR updated if a decision changed."
            )
            gh(
                [f"{base}/issues", "--method", "POST"],
                {
                    "title": row["title"],
                    "body": body,
                    "labels": row["labels"].split(";"),
                    "milestone": ms_number[row["milestone"]],
                },
                a.dry_run,
            )
            print("issue +", row["title"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
