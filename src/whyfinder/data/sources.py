"""The raw files Whyfinder downloads (docs/spec/03_DATA.md).

The UCSD McAuley Lab publishes no licence for these files and asks users to cite the papers in
CITATION.cff. They are downloaded by script, verified by SHA-256 and never committed.
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_URL = "https://mcauleylab.ucsd.edu/public_datasets/data/steam"


@dataclass(frozen=True)
class Source:
    """One raw file: where it comes from and what it is used for."""

    name: str
    filename: str
    url: str
    purpose: str


SOURCES: dict[str, Source] = {
    source.name: source
    for source in (
        Source(
            "reviews",
            "steam_reviews.json.gz",
            f"{BASE_URL}/steam_reviews.json.gz",
            "Version 2 reviews: interactions (review = positive, hours = confidence), RAG corpus",
        ),
        Source(
            "games",
            "steam_games.json.gz",
            f"{BASE_URL}/steam_games.json.gz",
            "Version 2 game metadata: titles, tags, genres, developers, publishers, prices, dates",
        ),
        Source(
            "au_items",
            "australian_users_items.json.gz",
            f"{BASE_URL}/australian_users_items.json.gz",
            "Version 1 owned games with playtime: robustness dataset",
        ),
        Source(
            "au_reviews",
            "australian_user_reviews.json.gz",
            f"{BASE_URL}/australian_user_reviews.json.gz",
            "Version 1 recommend labels: explanation sanity check",
        ),
        Source(
            "bundles",
            "bundle_data.json.gz",
            f"{BASE_URL}/bundle_data.json.gz",
            "Bundle co-membership: optional graph edges",
        ),
    )
}

#: The files the M0 pipeline needs; the others are fetched on demand (`--only`).
REQUIRED = ("reviews", "games")
