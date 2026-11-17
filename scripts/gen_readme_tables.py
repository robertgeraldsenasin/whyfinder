"""Regenerate the README results table from results/*.json.

Each results file is {"model": str, "split": "test", "metrics": {name: {"mean": float,
"lo": float, "hi": float}}}. With --check, exit 1 if the README is out of date (used by CI).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START, END = "<!-- results:start -->", "<!-- results:end -->"
EMPTY = "_Generated from `results/` at each release. None yet._"


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    before, rest = text.split(START, 1)
    _, after = rest.split(END, 1)
    new = f"{before}{START}\n{render(ROOT / 'results')}\n{END}{after}"
    if a.check:
        if new != text:
            print("README results table is out of date: run scripts/gen_readme_tables.py")
            return 1
        return 0
    readme.write_text(new, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
