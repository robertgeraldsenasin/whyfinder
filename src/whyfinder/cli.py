"""Command-line entry point: `whyfinder`.

Commands are added milestone by milestone (docs/plan/ROADMAP.md): `data` (M0), `build` and
`eval`/`gate` (M1), `explain` (M2), `index` (M3), `serve` (M4); `export demo` feeds the web demo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from whyfinder import __version__
from whyfinder.data.fetch import fetch as fetch_files
from whyfinder.data.sources import REQUIRED, SOURCES

app = typer.Typer(help="Whyfinder: find your next game. Know why.", no_args_is_help=True)
data_app = typer.Typer(help="Data pipeline (docs/spec/03_DATA.md).", no_args_is_help=True)
app.add_typer(data_app, name="data")

RAW = Path("data/raw")
INTERIM = Path("data/interim")
PROCESSED = Path("data/processed")
CI = Path("data/ci")
CHECKSUMS = Path("data/checksums.txt")
SPLIT_JSON = Path("data/split.json")
STATS_JSON = Path("data/stats.json")
ParamsOption = Annotated[Path, typer.Option("--params", help="Parameter file.")]


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.callback()
def main() -> None:
    """Whyfinder command line."""


@data_app.command("fetch")
def data_fetch(
    out: Annotated[Path, typer.Option(help="Directory for the raw files.")] = RAW,
    checksums: Annotated[Path, typer.Option(help="sha256sum-style file.")] = CHECKSUMS,
    only: Annotated[list[str] | None, typer.Option(help="Fetch only these sources.")] = None,
    record: Annotated[bool, typer.Option(help="Record checksums for new files.")] = False,
) -> None:
    """Download the raw files and verify their SHA-256 (FR-01)."""
    names = only or list(REQUIRED)
    unknown = [n for n in names if n not in SOURCES]
    if unknown:
        raise typer.BadParameter(f"unknown source(s): {', '.join(unknown)}", param_hint="--only")
    for result in fetch_files(out, checksums, names, record=record):
        typer.echo(f"{result.action:10s} {result.path.name}  {result.sha256}")
