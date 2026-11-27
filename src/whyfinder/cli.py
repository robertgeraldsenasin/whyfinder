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


RELEASE_ENV = "WHYFINDER_RELEASE"
SPLITS = ("valid", "test", "cold-valid", "cold-test")


@app.command("eval")
def eval_command(
    data: Annotated[
        Path, typer.Option(help="Directory with train/valid/test/cold/games Parquet.")
    ] = CI,
    split: Annotated[str, typer.Option(help="valid, test, cold-valid or cold-test.")] = "valid",
    out: Annotated[Path, typer.Option(help="Report JSON (per-user metrics included).")] = Path(
        "eval.json"
    ),
    models: Annotated[str, typer.Option(help="Comma-separated models (default: all).")] = "",
    item_cap: Annotated[int | None, typer.Option(help="Override data.item_cap.")] = None,
    max_users: Annotated[int | None, typer.Option(help="Override eval.max_users.")] = None,
    gate: Annotated[
        bool, typer.Option(help="Use the PR gate's item cap (eval.ci_item_cap).")
    ] = False,
    params: ParamsOption = Path("params.yaml"),
) -> None:
    """Build every model on train and score held-out users (FR-19). The test split is sealed."""
    import json
    import os

    import pandas as pd

    from whyfinder.eval.harness import MODELS, eval_set, evaluate

    if split not in SPLITS:
        raise typer.BadParameter(f"split must be one of {', '.join(SPLITS)}", param_hint="--split")
    if split.endswith("test") and os.environ.get(RELEASE_ENV) != "1":
        raise typer.BadParameter(
            "the test split is sealed: it is scored only by release.yml", param_hint="--split"
        )
    p = load_params(params)
    train = pd.read_parquet(data / "train.parquet")
    if split.startswith("cold-"):
        cold = pd.read_parquet(data / "cold.parquet")
        holdout = cold.loc[cold["part"] == split.removeprefix("cold-")]
    else:
        holdout = pd.read_parquet(data / f"{split}.parquet")
    games = pd.read_parquet(data / "games.parquet")
    if item_cap is not None:
        cap = item_cap
    else:
        cap = param(p, "eval.ci_item_cap" if gate else "data.item_cap", int)
    limit = max_users if max_users is not None else param(p, "eval.max_users", int)
    es = eval_set(
        train,
        holdout,
        item_cap=cap,
        alpha=param(p, "data.confidence.alpha", float),
        eps=param(p, "data.confidence.eps", float),
        max_users=limit,
    )
    if not es.users:
        raise typer.BadParameter("no held-out users inside the item cap", param_hint="--data")
    only = tuple(m for m in models.split(",") if m) or MODELS
    report = evaluate(es, games, p, seed=param(p, "seed", int), only=only)
    report["split"] = split
    report["sample"] = f"{split} users from {data}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, separators=(",", ":"), sort_keys=True) + "\n")
    for name, block in report["models"].items():
        m = block["means"]
        typer.echo(
            f"{name:11s} NDCG@10 {m['ndcg_at_10']:.4f}  Recall@20 {m['recall_at_20']:.4f}  "
            f"MRR {m['mrr']:.4f}  ILD@10 {m['ild_at_10']:.4f}  "
            f"coverage {block['coverage_at_10']:.4f}  build {block['build_seconds']:.1f}s"
        )
    typer.echo(f"{len(es.users)} users, {es.n_items} games; wrote {out}")


@app.command("gate")
def gate_command(
    head: Annotated[Path, typer.Option(help="This PR's eval report.")],
    base: Annotated[Path | None, typer.Option(help="Main's eval report, if main has one.")] = None,
    out: Annotated[Path, typer.Option(help="Markdown for the PR comment.")] = Path("gate.md"),
    superiority: Annotated[bool, typer.Option(help="Require improvement (model:gainer).")] = False,
    params: ParamsOption = Path("params.yaml"),
) -> None:
    """Compare head with base user by user; exit 1 when the gate fails (FR-20)."""
    import json

    from whyfinder.eval.gate import compare

    p = load_params(params)
    margins = {k: float(v) for k, v in p["eval"]["margins"].items()}
    explain_margins = {k: float(v) for k, v in p["eval"].get("explain_margins", {}).items()}
    base_report = json.loads(base.read_text()) if base is not None and base.exists() else None
    verdict = compare(
        base_report,
        json.loads(head.read_text()),
        margins=margins,
        resamples=param(p, "eval.bootstrap_resamples", int),
        seed=param(p, "seed", int),
        superiority=superiority,
        explain_margins=explain_margins,
    )
    out.write_text(verdict.markdown)
    typer.echo(verdict.markdown)
    if not verdict.passed:
        raise typer.Exit(1)


@app.command("results")
def results_command(
    report: Annotated[Path, typer.Option(help="An eval report on the sealed test split.")],
    out: Annotated[Path, typer.Option(help="Directory for one JSON per model.")] = Path("results"),
    params: ParamsOption = Path("params.yaml"),
) -> None:
    """Write results/<model>.json (means with 95% intervals) and results/targets/<split>.json
    (each ADR-0006 target, met or not) for the README tables."""
    import json

    from whyfinder.eval.results import summarize, targets

    p = load_params(params)
    data = json.loads(report.read_text())
    split = str(data.get("split", "test"))
    resamples, seed = param(p, "eval.bootstrap_resamples", int), param(p, "seed", int)
    rows = summarize(data, split, resamples=resamples, seed=seed)
    out.mkdir(parents=True, exist_ok=True)
    for row in rows:
        path = out / f"{row['model']}.json"
        path.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
        typer.echo(f"wrote {path}")
    goals = targets(data, resamples=resamples, seed=seed)
    path = out / "targets" / f"{split}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(goals, indent=2, ensure_ascii=False) + "\n")
    met = sum(1 for g in goals["targets"] if g["met"])
    typer.echo(f"wrote {path}: {met} of {len(goals['targets'])} targets met")


@app.command("tune")
def tune_command(
    data: Annotated[Path, typer.Option(help="Directory with train/valid/games Parquet.")] = CI,
    out: Annotated[
        Path, typer.Option(help="Every candidate's score and the chosen values.")
    ] = Path("tune.json"),
    item_cap: Annotated[int | None, typer.Option(help="Override data.item_cap.")] = None,
    gate: Annotated[
        bool, typer.Option(help="Use the PR gate's item cap (eval.ci_item_cap).")
    ] = False,
    params: ParamsOption = Path("params.yaml"),
) -> None:
    """Search the grids in params.yaml (tune.*) on the validation split; never on test."""
    import json

    import pandas as pd

    from whyfinder.eval.harness import eval_set
    from whyfinder.eval.tune import tune

    p = load_params(params)
    if item_cap is not None:
        cap = item_cap
    else:
        cap = param(p, "eval.ci_item_cap" if gate else "data.item_cap", int)
    es = eval_set(
        pd.read_parquet(data / "train.parquet"),
        pd.read_parquet(data / "valid.parquet"),
        item_cap=cap,
        alpha=param(p, "data.confidence.alpha", float),
        eps=param(p, "data.confidence.eps", float),
        max_users=param(p, "tune.max_users", int),
    )
    if not es.users:
        raise typer.BadParameter("no validation users inside the item cap", param_hint="--data")
    report = tune(es, pd.read_parquet(data / "games.parquet"), p, seed=param(p, "seed", int))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for name, rows in report["grids"].items():
        for row in rows:
            typer.echo(f"{name:6s} " + "  ".join(f"{k}={v}" for k, v in row.items()))
    typer.echo("best: " + ", ".join(f"{k}={v}" for k, v in report["best"].items()))
    typer.echo(
        f"{report['users']} users, {report['games']} games, {report['seconds']}s; wrote {out}"
    )


serve_app = typer.Typer(help="The REST API (docs/spec/12_API.md).", no_args_is_help=True)
app.add_typer(serve_app, name="serve")
OPENAPI = Path("docs/openapi.json")
SliceOption = Annotated[Path, typer.Option("--slice", help="The demo slice the API serves.")]


@serve_app.command("run")
def serve_run(
    host: Annotated[str, typer.Option(help="Interface to bind.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to listen on.")] = 8000,
    slice_path: SliceOption = WEB_SLICE,
    params: ParamsOption = Path("params.yaml"),
) -> None:
    """Serve the API (needs the `serve` group); reviews.json next to the slice adds /reviews and
    quoted evidence, after about 20 s of indexing. With WHYFINDER_LLM_MODEL set (and optionally
    WHYFINDER_LLM_URL), explanations are generated by that Ollama model and checked.
    WHYFINDER_CORS_ORIGINS (comma-separated) replaces the browser origins allowed to call it."""
    import os

    import uvicorn

    from whyfinder.rag.generate import Ollama
    from whyfinder.serve.app import create_app, origins
    from whyfinder.serve.model import ServedModel

    reviews = slice_path.parent / "reviews.json"
    model = ServedModel.load(slice_path, params, reviews if reviews.exists() else None)
    name = os.environ.get("WHYFINDER_LLM_MODEL")
    url = os.environ.get("WHYFINDER_LLM_URL", "http://127.0.0.1:11434")
    llm = Ollama(name, url=url) if name else None
    api = create_app(model, llm=llm, cors=origins(os.environ))
    uvicorn.run(api, host=host, port=port, proxy_headers=True)


@serve_app.command("openapi")
def serve_openapi(
    out: Annotated[Path, typer.Option(help="Where the OpenAPI document goes.")] = OPENAPI,
    check: Annotated[
        bool, typer.Option(help="Fail with a diff if the committed document is out of date.")
    ] = False,
    slice_path: SliceOption = WEB_SLICE,
    params: ParamsOption = Path("params.yaml"),
) -> None:
    """Write the OpenAPI document (FR-21), or check the committed one against the code."""
    import difflib
    import json

    from whyfinder.serve.app import create_app
    from whyfinder.serve.model import ServedModel

    api = create_app(ServedModel.load(slice_path, params), git_sha="openapi")
    text = json.dumps(api.openapi(), indent=2, sort_keys=True) + "\n"
    if check:
        old = out.read_text() if out.exists() else ""
        if old != text:
            diff = difflib.unified_diff(
                old.splitlines(keepends=True), text.splitlines(keepends=True), str(out), "code"
            )
            typer.echo("".join(diff))
            typer.echo(f"{out} is out of date: run `whyfinder serve openapi`", err=True)
            raise typer.Exit(1)
        typer.echo(f"{out} matches the code")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    typer.echo(f"wrote {out}")


rag_app = typer.Typer(help="Grounded explanations (docs/spec/06_RAG.md).", no_args_is_help=True)
app.add_typer(rag_app, name="rag")
LLM_CACHE = Path("data/llm/cache.jsonl")
RAG_EVAL = Path("results/validation/rag-eval.json")


@rag_app.command("eval")
def rag_eval(
    mode: Annotated[
        str, typer.Option(help="replay: answers from the cache only (CI); fill: ask the model.")
    ] = "replay",
    model_name: Annotated[str, typer.Option("--model", help="Ollama model.")] = "llama3.2:3b",
    url: Annotated[str, typer.Option(help="Ollama server.")] = "http://127.0.0.1:11434",
    cases: Annotated[int, typer.Option(help="Picks to explain.")] = 60,
    cache: Annotated[Path, typer.Option(help="Generation cache (JSON lines).")] = LLM_CACHE,
    out: Annotated[
        Path | None, typer.Option(help="Report path (default: per model, in results/validation).")
    ] = None,
    check: Annotated[bool, typer.Option(help="Fail if the report differs from `out`.")] = False,
    slice_path: SliceOption = WEB_SLICE,
    params: ParamsOption = Path("params.yaml"),
) -> None:
    """Explain seeded sample picks with the local model and measure faithfulness (FR-16, FR-17)."""
    import json
    from functools import partial

    from whyfinder.rag.evaluate import Case, run
    from whyfinder.rag.generate import Cache, Cached, Ollama, template
    from whyfinder.serve import grounding
    from whyfinder.serve.model import ServedModel

    if mode not in ("replay", "fill"):
        raise typer.BadParameter("mode is replay or fill")
    store = Cache.load(cache)
    if mode == "fill":
        llm = Ollama(model_name, url=url)
        backend = Cached(store, model_name, llm.digest, inner=llm)
    else:
        digests = {row["digest"] for row in store.entries.values() if row["model"] == model_name}
        if len(digests) != 1:
            typer.echo(
                f"{cache} has no single digest for {model_name}; run with --mode fill", err=True
            )
            raise typer.Exit(1)
        backend = Cached(store, model_name, digests.pop())
    p = load_params(params)
    served = ServedModel.load(slice_path, params, slice_path.parent / "reviews.json")
    seed = param(p, "seed", int)
    sample = []
    for history, explanation in grounding.sample(served, cases, seed=seed):
        pack, source = grounding.facts(served, history, explanation)
        sample.append(Case(pack, source, partial(template, pack)))
    report = run(sample, backend, seed=seed)
    if out is None:
        slug = "".join(c if c.isalnum() else "-" for c in model_name)
        out = RAG_EVAL.parent / f"rag-eval-{slug}.json"
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if mode == "fill":
        store.save()
    if check:
        if not out.exists() or out.read_text() != text:
            typer.echo(text)
            typer.echo(f"{out} does not match the replayed report", err=True)
            raise typer.Exit(1)
        typer.echo(f"{out} matches the replayed report")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    typer.echo(text)


labels_app = typer.Typer(
    help="Hand labels for review retrieval (#33; docs/labelling/retrieval.md).",
    no_args_is_help=True,
)
rag_app.add_typer(labels_app, name="labels")
LABELS = Path("data/labels/retrieval.csv")
LABEL_REPORT = Path("results/validation/retrieval-labels.json")


@labels_app.command("pool")
def labels_pool(
    out: Annotated[Path, typer.Option(help="The label sheet to write.")] = LABELS,
    queries: Annotated[int, typer.Option(help="Queries to sample.")] = 150,
    force: Annotated[bool, typer.Option(help="Replace a sheet that already has grades.")] = False,
    slice_path: SliceOption = WEB_SLICE,
    params: ParamsOption = Path("params.yaml"),
) -> None:
    """Sample (pick, aspect) queries as grounding asks them and write every review of each pick
    as a row to grade 0, 1 or 2."""
    from whyfinder.rag.labels import missing, read, write
    from whyfinder.serve import grounding
    from whyfinder.serve.model import ServedModel

    if out.exists() and not force:
        rows = read(out)
        if missing(rows)[0] < len(rows):
            typer.echo(f"{out} already has grades; pass --force to replace it", err=True)
            raise typer.Exit(1)
    served = ServedModel.load(slice_path, params, slice_path.parent / "reviews.json")
    seed = param(load_params(params), "seed", int)
    picked = grounding.label_queries(served, queries, seed=seed)
    rows = grounding.label_rows(served, picked)
    write(out, rows)
    typer.echo(f"{len(picked)} queries, {len(rows)} reviews to grade in {out}")


@labels_app.command("score")
def labels_score(
    sheet: Annotated[Path, typer.Option("--labels", help="The graded label sheet.")] = LABELS,
    out: Annotated[Path, typer.Option(help="Report path.")] = LABEL_REPORT,
    partial: Annotated[
        bool, typer.Option(help="Score the queries graded so far instead of failing.")
    ] = False,
    slice_path: SliceOption = WEB_SLICE,
    params: ParamsOption = Path("params.yaml"),
) -> None:
    """Cohen's kappa over the double-labelled reviews, and Recall@5 and nDCG@5 of the BM25, dense
    and fused rankings over the graded queries."""
    import json

    from whyfinder.rag.labels import DOUBLE, LabelError, missing, read, score
    from whyfinder.serve import grounding
    from whyfinder.serve.model import ServedModel

    try:
        rows = read(sheet)
    except (LabelError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    blank_a, blank_b = missing(rows)
    if (blank_a or blank_b) and not partial:
        typer.echo(
            f"{sheet}: {blank_a} reviews still need a grade, and {blank_b} in the first "
            f"{DOUBLE} queries a second grade; pass --partial to score what is there",
            err=True,
        )
        raise typer.Exit(1)
    served = ServedModel.load(slice_path, params, slice_path.parent / "reviews.json")
    report = score(rows, grounding.label_rankings(served, rows))
    report["complete"] = not (blank_a or blank_b)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    typer.echo(text)
