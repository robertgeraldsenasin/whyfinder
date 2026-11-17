"""Clean parsed reviews into interactions and parsed metadata into the catalogue (FR-02).

Rules (docs/spec/03_DATA.md): drop rows without a user or a game; keep only games with metadata;
pseudonymise usernames with a salted SHA-256; dedupe (user, game) keeping the most hours; clip hours
at the 99.9th percentile. Dates that don't parse become NaT and are counted.
"""

from __future__ import annotations

import hashlib
import html
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

DATE_FORMATS = ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%d %B, %Y", "%d %b, %Y")


@dataclass(frozen=True)
class CleanStats:
    """Counts and coverage from cleaning; written into data/stats.json."""

    rows_in: int
    dropped_no_user: int
    dropped_no_game: int
    dropped_unknown_game: int
    duplicates_removed: int
    rows_out: int
    users: int
    games: int
    date_coverage: float
    hours_coverage: float
    hours_clip: float
    date_min: str | None
    date_max: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_dates(raw: pd.Series) -> pd.Series:
    """Parse date strings in any of the known formats; unparseable values become NaT."""
    out = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns]")
    remaining = raw.notna()
    for fmt in DATE_FORMATS:
        if not remaining.any():
            break
        parsed = pd.to_datetime(raw[remaining], format=fmt, errors="coerce")
        hit = parsed.notna()
        out.loc[parsed.index[hit]] = parsed[hit].astype("datetime64[ns]")
        remaining.loc[parsed.index[hit]] = False
    return out


def hash_user(username: str, salt: str) -> str:
    """Salted SHA-256 of a username, 16 hex characters (64 bits; collisions negligible here)."""
    return hashlib.sha256(f"{salt}\x00{username}".encode()).hexdigest()[:16]


def clean_interactions(
    reviews: pd.DataFrame,
    known_games: set[int],
    *,
    salt: str,
    clip_quantile: float = 0.999,
) -> tuple[pd.DataFrame, CleanStats]:
    """Parsed reviews → one row per (user, game), sorted by (user, game).

    Output columns: user (hashed), game, hours (clipped, 0 when missing), hours_missing, date (NaT
    when missing), review_id (the kept review).
    """
    if not 0.0 < clip_quantile <= 1.0:
        raise ValueError("clip_quantile must be in (0, 1]")
    rows_in = len(reviews)
    no_user = reviews["username"].isna()
    df = reviews.loc[~no_user]
    no_game = df["game"].isna()
    df = df.loc[~no_game]
    unknown = ~df["game"].isin(list(known_games))
    df = df.loc[~unknown]

    df = pd.DataFrame(
        {
            "user": [hash_user(name, salt) for name in df["username"]],
            "game": df["game"].astype("int64").to_numpy(),
            "hours": df["hours"].astype("float64").to_numpy(),
            "date": parse_dates(df["date"]).to_numpy(),
            "review_id": df["review_id"].astype("int64").to_numpy(),
        }
    )
    df = df.sort_values(
        ["user", "game", "hours", "date", "review_id"],
        ascending=[True, True, False, False, True],
        na_position="last",
        kind="mergesort",
    )
    deduped = df.drop_duplicates(["user", "game"], keep="first")
    duplicates = len(df) - len(deduped)

    hours = deduped["hours"]
    present = hours.dropna()
    clip = float(np.quantile(present.to_numpy(), clip_quantile)) if len(present) else 0.0
    out = pd.DataFrame(
        {
            "user": deduped["user"].astype("str").to_numpy(),
            "game": deduped["game"].to_numpy(),
            "hours": hours.clip(lower=0.0, upper=clip).fillna(0.0).to_numpy(),
            "hours_missing": hours.isna().to_numpy(),
            "date": deduped["date"].to_numpy(),
            "review_id": deduped["review_id"].to_numpy(),
        }
    ).reset_index(drop=True)

    n = len(out)
    dates = out["date"].dropna()
    stats = CleanStats(
        rows_in=rows_in,
        dropped_no_user=int(no_user.sum()),
        dropped_no_game=int(no_game.sum()),
        dropped_unknown_game=int(unknown.sum()),
        duplicates_removed=int(duplicates),
        rows_out=n,
        users=int(out["user"].nunique()),
        games=int(out["game"].nunique()),
        date_coverage=float(len(dates) / n) if n else 0.0,
        hours_coverage=float((~out["hours_missing"]).mean()) if n else 0.0,
        hours_clip=clip,
        date_min=dates.min().strftime("%Y-%m-%d") if len(dates) else None,
        date_max=dates.max().strftime("%Y-%m-%d") if len(dates) else None,
    )
    return out, stats


def _unescape_text(text: str) -> str:
    # Some raw strings are escaped twice ("&amp;amp;"): decode until nothing changes.
    for _ in range(3):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    return text


def unescape(value: object) -> object:
    """Decode HTML entities ("Heroes &amp; Generals"); lists element-wise; None stays None."""
    if isinstance(value, str):
        return _unescape_text(value)
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, list | tuple):
        return [_unescape_text(v) if isinstance(v, str) else v for v in value]
    return value


def clean_games(games: pd.DataFrame) -> pd.DataFrame:
    """Parsed metadata → catalogue sorted by game ID, with `release_year`, a non-empty title and
    HTML entities decoded (the raw metadata has "&amp;" in titles, developers and tags)."""
    df = games.sort_values("game", kind="mergesort").drop_duplicates("game").copy()
    for column in ("title", "developer", "publisher", "genres", "tags", "specs"):
        if column in df:
            df[column] = df[column].map(unescape)
    df["title"] = df["title"].fillna(df["game"].map(lambda g: f"App {g}"))
    year = df["release_date"].astype("str").str.extract(r"((?:19|20)\d\d)", expand=False)
    df["release_year"] = pd.to_numeric(year, errors="coerce").astype("Int64")
    for column in ("genres", "tags", "specs"):
        df[column] = df[column].map(lambda v: list(v) if v is not None else [])
    return df.reset_index(drop=True)
