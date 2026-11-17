"""The data stages as file-to-file functions; `dvc.yaml` runs them through the CLI.

Layout:

    data/raw/              downloaded files (never committed)
    data/interim/          parsed tables
    data/processed/        cleaned, k-cored, split tables and X_train
    data/ci/               the pinned CI subsample (published as release asset data-ci-v1)
    data/checksums.txt     SHA-256 of every raw file          (committed)
    data/split.json        cut-offs, counts and table hashes  (committed)
    data/stats.json        every count the README may quote    (committed)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import scipy.sparse as sp

from whyfinder.data import contracts
from whyfinder.data.clean import clean_games, clean_interactions
from whyfinder.data.features import build_features
from whyfinder.data.kcore import kcore
from whyfinder.data.parse import parse_games, parse_reviews
from whyfinder.data.sources import SOURCES
from whyfinder.data.split import time_split
from whyfinder.data.subsample import subsample

SPLITS = ("train", "valid", "test", "cold")


def write_json(path: Path, payload: object) -> None:
    """Deterministic JSON: sorted keys, two-space indent, trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stage_parse(raw: Path, interim: Path, *, workers: int, tolerance: float) -> dict[str, Any]:
    reviews = parse_reviews(
        raw / SOURCES["reviews"].filename,
        interim / "reviews.parquet",
        interim / "review_text.parquet",
        workers=workers,
        tolerance=tolerance,
    )
    games = parse_games(raw / SOURCES["games"].filename, interim / "games.parquet")
    stats = {
        name: {"lines": s.lines, "malformed": s.malformed, "written": s.written}
        for name, s in (("reviews", reviews), ("games", games))
    }
    write_json(interim / "parse_stats.json", stats)
    return stats


def stage_clean(
    interim: Path, processed: Path, *, salt: str, clip_quantile: float
) -> dict[str, Any]:
    games = clean_games(pd.read_parquet(interim / "games.parquet"))
    contracts.check_games(games)
    reviews = pd.read_parquet(
        interim / "reviews.parquet", columns=["review_id", "username", "game", "hours", "date"]
    )
    interactions, stats = clean_interactions(
        reviews, set(games["game"].tolist()), salt=salt, clip_quantile=clip_quantile
    )
    contracts.check_interactions(interactions, games)
    processed.mkdir(parents=True, exist_ok=True)
    games.to_parquet(processed / "games.parquet", index=False)
    interactions.to_parquet(processed / "interactions_clean.parquet", index=False)
    payload = {**stats.to_dict(), "catalogue_games": len(games)}
    write_json(processed / "clean_stats.json", payload)
    return payload


def stage_kcore(processed: Path, *, k: int) -> dict[str, Any]:
    df = pd.read_parquet(processed / "interactions_clean.parquet")
    core, passes = kcore(df, k)
    core = core.reset_index(drop=True)
    contracts.check_kcore(core, k)
    core.to_parquet(processed / "interactions.parquet", index=False)
    payload = {
        "k": k,
        "passes": passes,
        "rows_in": len(df),
        "rows_out": len(core),
        "users": int(core["user"].nunique()),
        "games": int(core["game"].nunique()),
        "density": len(core) / (core["user"].nunique() * core["game"].nunique()),
    }
    write_json(processed / "kcore_stats.json", payload)
    return payload


def stage_split(
    processed: Path,
    split_json: Path,
    *,
    valid_quantile: float,
    test_quantile: float,
    cold_max: int,
    max_missing_date: float,
) -> dict[str, Any]:
    df = pd.read_parquet(processed / "interactions.parquet")
    split = time_split(
        df,
        valid_quantile=valid_quantile,
        test_quantile=test_quantile,
        cold_max=cold_max,
        max_missing_date=max_missing_date,
    )
    t1, t2 = split.info["t1"], split.info["t2"]
    contracts.check_split(
        split.train,
        split.valid,
        split.test,
        t1=t1 if isinstance(t1, str) else None,
        t2=t2 if isinstance(t2, str) else None,
        cold_max=cold_max,
    )
    for name in SPLITS:
        getattr(split, name).to_parquet(processed / f"{name}.parquet", index=False)
    write_json(split_json, split.info)
    return split.info


def stage_features(processed: Path, *, item_cap: int, alpha: float, eps: float) -> dict[str, Any]:
    train = pd.read_parquet(processed / "train.parquet")
    features = build_features(train, item_cap=item_cap, alpha=alpha, eps=eps)
    sp.save_npz(processed / "X_train.npz", features.X, compressed=True)
    features.items.to_parquet(processed / "items.parquet", index=False)
    features.users.to_parquet(processed / "users.parquet", index=False)
    capped = int(features.X.nnz)
    payload = {
        "item_cap": item_cap,
        "items": len(features.items),
        "users": len(features.users),
        "nnz": capped,
        "train_rows_covered": capped / len(train) if len(train) else 0.0,
        "confidence": {"alpha": alpha, "eps": eps},
    }
    write_json(processed / "features_stats.json", payload)
    return payload


def stage_subsample(processed: Path, out: Path, *, fraction: float) -> dict[str, Any]:
    tables = {name: pd.read_parquet(processed / f"{name}.parquet") for name in SPLITS}
    sampled = subsample(tables, fraction)
    out.mkdir(parents=True, exist_ok=True)
    for name, df in sampled.items():
        df.to_parquet(out / f"{name}.parquet", index=False)
    games = pd.read_parquet(processed / "games.parquet")
    games.to_parquet(out / "games.parquet", index=False)
    payload = {
        "fraction": fraction,
        "rows": {name: len(df) for name, df in sampled.items()},
        "users": {name: int(df["user"].nunique()) for name, df in sampled.items()},
        "games": len(games),
    }
    write_json(out / "manifest.json", payload)
    return payload


def stage_stats(
    interim: Path, processed: Path, split_json: Path, ci: Path, stats_json: Path
) -> dict[str, Any]:
    payload = {
        "parse": read_json(interim / "parse_stats.json"),
        "clean": read_json(processed / "clean_stats.json"),
        "kcore": read_json(processed / "kcore_stats.json"),
        "split": read_json(split_json),
        "features": read_json(processed / "features_stats.json"),
        "ci_subsample": read_json(ci / "manifest.json"),
    }
    write_json(stats_json, payload)
    return payload
