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
from whyfinder.export.demo import demo_slice
from whyfinder.params import load_params, param

app = typer.Typer(help="Whyfinder: find your next game. Know why.", no_args_is_help=True)
data_app = typer.Typer(help="Data pipeline (docs/spec/03_DATA.md).", no_args_is_help=True)
app.add_typer(data_app, name="data")
export_app = typer.Typer(help="Exports for the web demo (ADR-0015).", no_args_is_help=True)
app.add_typer(export_app, name="export")

RAW = Path("data/raw")
INTERIM = Path("data/interim")
PROCESSED = Path("data/processed")
CI = Path("data/ci")
CHECKSUMS = Path("data/checksums.txt")
SPLIT_JSON = Path("data/split.json")
STATS_JSON = Path("data/stats.json")
DEMO_SLICE = Path("data/export/demo-slice.json")
DEMO_REVIEWS = Path("data/export/reviews.json")
WEB_SLICE = Path("web/public/data/demo-slice.json")
WEB_MODEL = Path("web/public/data/model.json")
WEB_GOLDENS = Path("web/src/engine/__goldens__/goldens.json")
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


@data_app.command("subsample")
def data_subsample(params: ParamsOption = Path("params.yaml")) -> None:
    """Write the pinned CI subsample (NFR-01)."""
    fraction = param(load_params(params), "data.ci_user_fraction", float)
    s = pipeline.stage_subsample(PROCESSED, CI, fraction=fraction)
    typer.echo(f"CI subsample ({fraction:.0%} of users): {s['rows']}")


@data_app.command("stats")
def data_stats() -> None:
    """Merge every stage's counts into data/stats.json."""
    pipeline.stage_stats(INTERIM, PROCESSED, SPLIT_JSON, CI, STATS_JSON)
    typer.echo(f"wrote {STATS_JSON}")


@export_app.command("demo")
def export_demo(
    out: Annotated[Path, typer.Option(help="Where to write the slice.")] = DEMO_SLICE,
    params: ParamsOption = Path("params.yaml"),
) -> None:
    """Write the demo slice: top games, co-play Gram matrix, metadata and layout (ADR-0015)."""
    import json

    import pandas as pd

    p = load_params(params)
    payload = demo_slice(
        pd.read_parquet(PROCESSED / "train.parquet", columns=["user", "game"]),
        pd.read_parquet(PROCESSED / "games.parquet"),
        n_games=param(p, "demo.games", int),
        tags_per_game=param(p, "graph.tags_per_game", int),
        neighbors=param(p, "demo.layout_neighbors", int),
        iterations=param(p, "demo.layout_iterations", int),
        split=pipeline.read_json(SPLIT_JSON),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
    typer.echo(f"wrote {out}: {len(payload['games'])} games from {payload['users']} users")


@export_app.command("model")
def export_model(
    slice_path: Annotated[
        Path, typer.Option("--slice", help="Demo slice to build on.")
    ] = WEB_SLICE,
    model_out: Annotated[Path, typer.Option(help="Model constants for the demo.")] = WEB_MODEL,
    goldens_out: Annotated[
        Path, typer.Option(help="Goldens for the TypeScript engine.")
    ] = WEB_GOLDENS,
    params: ParamsOption = Path("params.yaml"),
) -> None:
    """Build the glass-box model on the slice in Python; write its constants and the goldens."""
    import json

    from whyfinder.export.model import build_model, goldens, model_file, model_params

    model = build_model(json.loads(slice_path.read_text()), model_params(load_params(params)))
    for path, payload in ((model_out, model_file(model)), (goldens_out, goldens(model))):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
    typer.echo(f"c_B={model.c_B:.6g} c_Pi={model.c_Pi:.6g}; wrote {model_out} and {goldens_out}")


@export_app.command("reviews")
def export_reviews(
    out: Annotated[Path, typer.Option(help="Where to write the evidence.")] = DEMO_REVIEWS,
    slice_path: Annotated[Path, typer.Option("--slice", help="Demo slice.")] = DEMO_SLICE,
    params: ParamsOption = Path("params.yaml"),
) -> None:
    """Write review evidence for the demo slice: community terms and short quotes per game."""
    import json

    import pandas as pd

    from whyfinder.data.clean import hash_user, parse_dates
    from whyfinder.export.reviews import review_evidence

    p = load_params(params)
    games = json.loads(slice_path.read_text())["games"]
    ids = [int(g["id"]) for g in games]
    t1 = pd.Timestamp(str(pipeline.read_json(SPLIT_JSON)["t1"]))
    meta = pd.read_parquet(
        INTERIM / "reviews.parquet",
        columns=["review_id", "username", "game", "hours", "date"],
        filters=[("game", "in", ids)],
    )
    meta = meta.loc[meta["username"].notna()]
    meta["date"] = parse_dates(meta["date"])
    meta = meta.loc[meta["date"] < t1]
    # Text only for the reviews that will be read (the first per game by ID); the rest still
    # count for which other games each player reviewed.
    cap = param(p, "demo.reviews_per_game", int)
    meta = meta.sort_values("review_id", kind="mergesort")
    wanted = meta.groupby("game", sort=False).head(cap)["review_id"].tolist()
    text = pd.read_parquet(
        INTERIM / "review_text.parquet",
        columns=["review_id", "text"],
        filters=[("review_id", "in", wanted)],
    )
    df = meta.merge(text, on="review_id", how="left")
    salt = param(p, "data.user_salt", str)
    df = pd.DataFrame(
        {
            "review_id": df["review_id"].astype("int64"),
            "user": [hash_user(u, salt) for u in df["username"]],
            "game": df["game"].astype("int64"),
            "hours": df["hours"].fillna(0.0).astype("float64"),
            "year": df["date"].dt.year,
            "text": df["text"],
        }
    )
    payload = review_evidence(
        df,
        games,
        quotes_per_game=param(p, "demo.quotes_per_game", int),
        terms_per_game=param(p, "demo.terms_per_game", int),
        max_reviews_per_game=cap,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False) + "\n"
    )
    quotes = sum(len(g["quotes"]) for g in payload["games"].values())
    read = int(df["text"].notna().sum())
    typer.echo(
        f"wrote {out}: {quotes} quotes from {read} of {len(df)} reviews before {t1:%Y-%m-%d}"
    )
