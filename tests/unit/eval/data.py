"""A small synthetic dataset for the evaluation tests: four taste clusters over 32 games."""

from __future__ import annotations

import numpy as np
import pandas as pd

TAGS = [
    ["Roguelike", "Indie"],
    ["Strategy", "Turn-Based"],
    ["Survival", "Open World"],
    ["Puzzle", "Indie"],
]


def synthetic(seed: int = 3) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """120 users in four taste clusters over 32 games; each user's last two games are held out."""
    rng = np.random.default_rng(seed)
    games = pd.DataFrame(
        {
            "game": np.arange(100, 132),
            "tags": [TAGS[g % 4] for g in range(32)],
            "genres": [["Action"] if g % 2 else ["Strategy"] for g in range(32)],
            "developer": [f"Studio {g % 6}" for g in range(32)],
            "publisher": [f"Pub {g % 3}" for g in range(32)],
        }
    )
    train, valid = [], []
    for u in range(120):
        cluster = u % 4
        pool = [100 + g for g in range(32) if g % 4 == cluster]
        others = [100 + g for g in range(32) if g % 4 != cluster]
        picked = (
            rng.choice(pool, size=6, replace=False).tolist() + rng.choice(others, size=1).tolist()
        )
        user = f"{u:08x}"
        train.extend((user, g, float(rng.integers(1, 200))) for g in picked[:5])
        valid.extend((user, g, 1.0) for g in picked[5:])
    columns = ["user", "game", "hours"]
    return pd.DataFrame(train, columns=columns), pd.DataFrame(valid, columns=columns), games
