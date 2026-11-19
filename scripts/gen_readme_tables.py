"""Regenerate the README results tables from results/.

Each results/*.json is {"model": str, "split": "test", "metrics": {name: {"mean": float,
"lo": float, "hi": float}}}; results/targets/test.json lists the ADR-0006 targets, met or not.
With --check, exit 1 if the README is out of date (used by CI).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START, END = "<!-- results:start -->", "<!-- results:end -->"
T_START, T_END = "<!-- targets:start -->", "<!-- targets:end -->"
EMPTY = "_Generated from `results/` at each release. None yet._"
MARK = {True: "met", False: "**not met**", None: "n/a"}


def render(results_dir: Path) -> str:
    files = sorted(results_dir.glob("*.json"))
    if not files:
        return EMPTY
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    names = sorted({m for r in rows for m in r["metrics"]})
    head = "| Model | " + " | ".join(names) + " |"
    sep = "| --- | " + " | ".join("---" for _ in names) + " |"
    lines = [head, sep]
    for r in rows:
        cells = []
        for n in names:
            m = r["metrics"].get(n)
            cells.append(f"{m['mean']:.4f} [{m['lo']:.4f}, {m['hi']:.4f}]" if m else "n/a")
        lines.append(f"| {r['model']} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n\n_Sealed test set, 95% bootstrap intervals._"


def render_targets(path: Path) -> str:
    if not path.exists():
        return EMPTY
    doc = json.loads(path.read_text(encoding="utf-8"))
    lines = ["| Target (ADR-0006) | Result | Evidence |", "| --- | --- | --- |"]
    lines += [
        f"| {row['target']} | {MARK[row['met']]} | {row['detail'] or ''} |"
        for row in doc["targets"]
    ]
    return "\n".join(lines) + f"\n\n_Sealed test set, {doc['users']:,} users, paired bootstrap._"


def replace(text: str, start: str, end: str, body: str) -> str:
    if start not in text:
        return text
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    return f"{before}{start}\n{body}\n{end}{after}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    new = replace(text, START, END, render(ROOT / "results"))
    new = replace(new, T_START, T_END, render_targets(ROOT / "results" / "targets" / "test.json"))
    if a.check:
        if new != text:
            print("README results table is out of date: run scripts/gen_readme_tables.py")
            return 1
        return 0
    readme.write_text(new, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
