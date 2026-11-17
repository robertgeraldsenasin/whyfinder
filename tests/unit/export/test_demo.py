from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from whyfinder.cli import app
from whyfinder.export.demo import (
    cosine,
    demo_slice,
    gram,
    layout,
    pack_upper,
    top_games,
    unpack_upper,
)


def train(seed: int = 5, users: int = 80, games: int = 30) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for u in range(users):
        cluster = u % 3  # three taste clusters → three regions on the map
        pool = [g for g in range(games) if g % 3 == cluster] + list(rng.choice(games, 2))
        rows.extend((f"{u:016x}", 100 + int(g)) for g in rng.choice(pool, size=6, replace=False))
    return pd.DataFrame(rows, columns=["user", "game"]).drop_duplicates()


def catalogue(games: int = 30) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game": np.arange(100, 100 + games, dtype="int64"),
            "title": [f"Game {i}" for i in range(games)],
            "developer": [f"Dev {i % 5}" for i in range(games)],
            "publisher": [None if i % 4 == 0 else f"Pub {i % 2}" for i in range(games)],
            "tags": [[f"tag{i % 7}", f"tag{i % 3}", "Indie", "x", "y"] for i in range(games)],
            "genres": [["Action"] for _ in range(games)],
            "release_year": pd.array(
                [2010 + i % 9 if i % 5 else None for i in range(games)], "Int64"
            ),
            "price": [float("nan") if i == 3 else 4.99 * (i % 4) for i in range(games)],
        }
    )


def test_top_games_by_count_then_id() -> None:
    df = pd.DataFrame({"user": list("aabbc"), "game": [1, 2, 2, 3, 3]})
    assert top_games(df, 2)["game"].tolist() == [2, 3]
    with pytest.raises(ValueError, match="at least 2"):
        top_games(df, 1)


def test_gram_counts_co_play_and_is_symmetric() -> None:
    df = pd.DataFrame({"user": ["a", "a", "b", "b", "b", "c"], "game": [1, 2, 1, 2, 3, 9]})
    G, users = gram(df, np.array([1, 2, 3]))
    assert users == 2
    assert G.tolist() == [[2, 2, 1], [2, 2, 1], [1, 1, 1]]


def test_pack_round_trip_and_bad_length() -> None:
    G = np.array([[3, 1, 0], [1, 2, 4], [0, 4, 5]])
    packed = pack_upper(G)
    assert packed == [3, 1, 0, 2, 4, 5]
    assert np.array_equal(unpack_upper(packed, 3), G)
    with pytest.raises(ValueError, match="does not fit"):
        unpack_upper(packed, 4)


def test_cosine_has_zero_diagonal_and_unit_scale() -> None:
    S = cosine(np.array([[4, 2], [2, 1]]))
    assert S[0, 0] == 0.0
    assert S[0, 1] == pytest.approx(2 / np.sqrt(4))


def test_layout_is_deterministic_bounded_and_clusters() -> None:
    df = train()
    ids = top_games(df, 30)["game"].to_numpy()
    G, _ = gram(df, ids)
    pos = layout(cosine(G), neighbors=5, iterations=150)
    assert np.array_equal(pos, layout(cosine(G), neighbors=5, iterations=150))
    assert pos.min() >= 0.04 - 1e-12
    assert pos.max() <= 0.96 + 1e-12
    cluster = (ids - 100) % 3
    centres = np.array([pos[cluster == c].mean(axis=0) for c in range(3)])
    within = np.mean(
        [np.linalg.norm(pos[cluster == c] - centres[c], axis=1).mean() for c in range(3)]
    )
    between = np.mean(
        [np.linalg.norm(centres[a] - centres[b]) for a, b in ((0, 1), (0, 2), (1, 2))]
    )
    assert between > within  # co-played games sit together


def test_layout_handles_tiny_inputs() -> None:
    assert layout(np.zeros((2, 2)), neighbors=3, iterations=5).shape == (2, 2)


def test_demo_slice_has_aggregates_only() -> None:
    payload = demo_slice(
        train(),
        catalogue(),
        n_games=12,
        tags_per_game=3,
        neighbors=4,
        iterations=50,
        split={"t1": "2017-01-01", "method": "global_time", "sha256": {"x": "secret"}},
    )
    games = payload["games"]
    assert len(games) == payload["gram"]["n"] == 12
    assert [g["id"] for g in games] == sorted(g["id"] for g in games)
    assert all(len(g["tags"]) <= 3 for g in games)
    assert len(payload["gram"]["packed_upper"]) == 12 * 13 // 2
    assert payload["split"] == {"t1": "2017-01-01", "method": "global_time"}
    text = json.dumps(payload)
    assert "0000000000000000" not in text  # no user IDs
    nulls = [g for g in games if g["price"] is None or g["year"] is None or g["publisher"] is None]
    assert nulls  # missing values become null, never NaN
    assert "NaN" not in text


def test_export_demo_cli(raw_dir: Path, params_file: Path) -> None:
    root = raw_dir.parents[1]
    params_file.write_text(
        params_file.read_text()
        + "graph: {tags_per_game: 5}\n"
        + "demo: {games: 8, layout_neighbors: 3, layout_iterations: 20}\n"
    )
    old = Path.cwd()
    os.chdir(root)
    try:
        runner = CliRunner()
        for stage in ("parse", "clean", "kcore", "split"):
            assert runner.invoke(app, ["data", stage]).exit_code == 0
        result = runner.invoke(app, ["export", "demo"])
        assert result.exit_code == 0, result.output
        payload = json.loads((root / "data" / "export" / "demo-slice.json").read_text())
        assert payload["gram"]["n"] == 8
    finally:
        os.chdir(old)
