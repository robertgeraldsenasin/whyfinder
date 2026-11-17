"""Command-line entry point: `whyfinder`.

Commands are added milestone by milestone (docs/plan/ROADMAP.md): `data` (M0), `build` and
`eval`/`gate` (M1), `explain` (M2), `index` (M3), `serve` (M4); `export demo` feeds the web demo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from whyfinder import __version__
from whyfinder.data import pipeline
from whyfinder.data.fetch import fetch as fetch_files
from whyfinder.data.sources import REQUIRED, SOURCES
from whyfinder.params import load_params, param

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


@data_app.command("parse")
def data_parse(
    workers: Annotated[int, typer.Option(help="Parser processes.")] = 1,
    params: ParamsOption = Path("params.yaml"),
) -> None:
    """Stream-parse the raw files into Parquet (FR-02)."""
    p = load_params(params)
    stats = pipeline.stage_parse(
        RAW, INTERIM, workers=workers, tolerance=param(p, "data.parse_tolerance", float)
    )
    for name, s in stats.items():
        typer.echo(f"{name}: {s['written']} rows, {s['malformed']} malformed of {s['lines']}")


@data_app.command("clean")
def data_clean(params: ParamsOption = Path("params.yaml")) -> None:
    """Dedupe, pseudonymise, clip hours; build the catalogue (FR-02)."""
    p = load_params(params)
    s = pipeline.stage_clean(
        INTERIM,
        PROCESSED,
        salt=param(p, "data.user_salt", str),
        clip_quantile=param(p, "data.hours_clip_quantile", float),
    )
    typer.echo(f"{s['rows_out']} interactions, {s['users']} users, {s['games']} games")
    typer.echo(f"date coverage {s['date_coverage']:.4f}, hours coverage {s['hours_coverage']:.4f}")


@data_app.command("kcore")
def data_kcore(params: ParamsOption = Path("params.yaml")) -> None:
    """Keep the k-core of users and games (FR-02)."""
    s = pipeline.stage_kcore(PROCESSED, k=param(load_params(params), "data.kcore", int))
    typer.echo(f"{s['rows_out']} interactions after {s['passes']} passes (k={s['k']})")


@data_app.command("split")
def data_split(params: ParamsOption = Path("params.yaml")) -> None:
    """Global time split into train, valid, test and cold (FR-03)."""
    p = load_params(params)
    info = pipeline.stage_split(
        PROCESSED,
        SPLIT_JSON,
        valid_quantile=param(p, "split.valid_quantile", float),
        test_quantile=param(p, "split.test_quantile", float),
        cold_max=param(p, "split.cold_max_train_items", int),
        max_missing_date=param(p, "split.max_missing_date", float),
    )
    typer.echo(f"{info['method']}: T1={info['t1']} T2={info['t2']} rows={info['rows']}")


@data_app.command("features")
def data_features(params: ParamsOption = Path("params.yaml")) -> None:
    """Build X_train with confidence weights and the item cap (FR-02, ADR-0004)."""
    p = load_params(params)
    s = pipeline.stage_features(
        PROCESSED,
        item_cap=param(p, "data.item_cap", int),
        alpha=param(p, "data.confidence.alpha", float),
        eps=param(p, "data.confidence.eps", float),
    )
    typer.echo(f"X_train: {s['users']} users × {s['items']} games, {s['nnz']} non-zeros")
