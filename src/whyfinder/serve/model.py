"""What the API serves: the glass-box model built by the Python core on the demo slice.

It is the same model the browser engine runs (the slice and params the goldens are made from), so a
pick and its reasons from the API equal the demo's for the same games. Histories from the API carry
no play time, so every liked game gets the confidence of zero hours.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from whyfinder.core.blend import confidence
from whyfinder.explain.attributions import Contribution, attributions
from whyfinder.explain.counterfactual import Counterfactual, greedy
from whyfinder.explain.paths import Path as GraphPath
from whyfinder.explain.paths import related_by
from whyfinder.export.model import Model, build_model, model_params
from whyfinder.params import load_params
from whyfinder.rag.reviews import ReviewIndex
from whyfinder.rag.reviews import build as build_reviews
from whyfinder.rerank.pipeline import Recommendation, recommend

MODEL_VERSION = "blend-slice-1"


@dataclass(frozen=True)
class Filters:
    tags: tuple[str, ...] = ()
    max_price: float | None = None
    year_min: int | None = None
    year_max: int | None = None

    def passes(self, game: dict[str, Any]) -> bool:
        """Unknown price or year fails a filter on it (the demo's rule too)."""
        price, year = game.get("price"), game.get("year")
        if self.max_price is not None and (price is None or price > self.max_price):
            return False
        if (self.year_min is not None or self.year_max is not None) and year is None:
            return False
        if self.year_min is not None and year is not None and year < self.year_min:
            return False
        if self.year_max is not None and year is not None and year > self.year_max:
            return False
        own = set(game.get("tags") or [])
        return all(t in own for t in self.tags)

    @property
    def active(self) -> bool:
        return bool(self.tags) or any(
            v is not None for v in (self.max_price, self.year_min, self.year_max)
        )


@dataclass(frozen=True)
class Explanation:
    pick: int
    rank: int | None
    score: float
    contributions: list[Contribution]
    counterfactual: Counterfactual
    paths: list[GraphPath]
    kept_for_variety: bool


class ServedModel:
    """The model plus the catalogue lookups the endpoints need."""

    def __init__(
        self,
        model: Model,
        *,
        hashes: dict[str, str],
        data_version: str,
        reviews: ReviewIndex | None = None,
        terms: dict[int, list[str]] | None = None,
    ) -> None:
        self.model = model
        self.reviews = reviews
        self.terms = terms or {}
        self.p = model.params
        self.ids = model.game_ids
        self.index = {gid: i for i, gid in enumerate(self.ids)}
        self.hashes = hashes
        self.data_version = data_version
        conf = self.p["confidence"]
        self.weight = float(confidence(np.array([0.0]), conf["alpha"], conf["eps"])[0])

    @classmethod
    def load(
        cls, slice_path: Path, params_path: Path, reviews_path: Path | None = None
    ) -> ServedModel:
        """Build the model; with a review export, also the review index (about 20 s for 6,000)."""
        raw = slice_path.read_bytes()
        slice_ = json.loads(raw)
        params = load_params(params_path)
        model = build_model(slice_, model_params(params))
        hashes = {
            slice_path.name: hashlib.sha256(raw).hexdigest(),
            params_path.name: hashlib.sha256(params_path.read_bytes()).hexdigest(),
        }
        t1 = slice_.get("split", {}).get("t1", "?")
        data_version = f"demo-slice v{slice_.get('version', '?')}, train split to {t1}"
        if reviews_path is None:
            return cls(model, hashes=hashes, data_version=data_version)
        raw_reviews = reviews_path.read_bytes()
        hashes[reviews_path.name] = hashlib.sha256(raw_reviews).hexdigest()
        games = json.loads(raw_reviews)["games"]
        index = build_reviews(games, model.game_ids, params["rag"], seed=int(params["seed"]))
        where = {gid: i for i, gid in enumerate(model.game_ids)}
        terms = {
            where[int(k)]: [str(t) for t, _ in g.get("terms", [])]
            for k, g in games.items()
            if int(k) in where
        }
        return cls(model, hashes=hashes, data_version=data_version, reviews=index, terms=terms)

    def aspects(self, pick: int, source: int, limit: int = 4) -> list[str]:
        """What the pick shares with a liked game: common tags (the pick's order), then the words
        both games' players use (06_RAG step 2)."""
        theirs = set(self.games[source].get("tags") or [])
        shared = [t for t in self.games[pick].get("tags") or [] if t in theirs]
        words = set(self.terms.get(source, []))
        shared += [w for w in self.terms.get(pick, []) if w in words and w not in shared]
        return shared[:limit]

    @property
    def games(self) -> list[dict[str, Any]]:
        return self.model.games

    def title(self, i: int) -> str:
        return str(self.games[i]["title"])

    def history(self, game_ids: list[int]) -> tuple[list[tuple[int, float]], list[int]]:
        """(index, weight) for known IDs in order, duplicates dropped; and the unknown IDs."""
        seen: set[int] = set()
        known, unknown = [], []
        for gid in game_ids:
            i = self.index.get(gid)
            if i is None:
                unknown.append(gid)
            elif i not in seen:
                seen.add(i)
                known.append((i, self.weight))
        return known, unknown

    def run(
        self, history: list[tuple[int, float]], *, k: int, filters: Filters, diversity: bool
    ) -> Recommendation:
        """The pipeline; without diversity the picks are the relevance-only top k (no DPP)."""
        allowed = [filters.passes(g) for g in self.games] if filters.active else None
        rec = recommend(
            history,
            self.model.M,
            vectors=self.model.vectors,
            game_ids=self.ids,
            k=k,
            n_candidates=int(self.p["candidates"]),
            theta=float(self.p["theta"]),
            allowed=allowed,
        )
        if diversity:
            return rec
        return Recommendation(
            scores=rec.scores,
            candidates=rec.candidates,
            relevance_top=rec.relevance_top,
            picks=list(rec.relevance_top),
            variety=[False] * len(rec.relevance_top),
            steps=[],
        )

    def contributions(self, history: list[tuple[int, float]], pick: int) -> list[Contribution]:
        return attributions(
            history,
            pick,
            self.model.M,
            self.model.B,
            self.model.Pi,
            beta=float(self.p["beta"]),
            c_B=self.model.c_B,
            c_Pi=self.model.c_Pi,
            game_ids=self.ids,
        )

    def explain(
        self, history: list[tuple[int, float]], pick: int, *, filters: Filters
    ) -> Explanation:
        rec = self.run(history, k=int(self.p["k"]), filters=filters, diversity=True)

        def pipeline(h: list[tuple[int, float]]) -> list[int]:
            return self.run(h, k=int(self.p["k"]), filters=filters, diversity=True).picks

        parts = self.contributions(history, pick)
        rank = rec.picks.index(pick) if pick in rec.picks else None
        cf = (
            greedy(pipeline, history, pick, [c.game for c in parts])
            if rank is not None
            else Counterfactual(pick, [], 0, [])
        )
        return Explanation(
            pick=pick,
            rank=rank,
            score=float(rec.scores[pick]),
            contributions=parts,
            counterfactual=cf,
            paths=related_by(self.model.graph, parts[0].game, pick) if parts else [],
            kept_for_variety=bool(rank is not None and rec.variety[rank]),
        )

    def search(self, q: str, limit: int = 10) -> list[int]:
        """Titles starting with q, then containing it; ties to the most reviewed, then by ID."""
        want = q.strip().lower()
        if not want:
            return []
        scored = []
        for i, g in enumerate(self.games):
            title = str(g["title"]).lower()
            at = title.find(want)
            if at >= 0:
                scored.append((0 if at == 0 else 1, -int(g.get("plays") or 0), self.ids[i], i))
        return [i for *_, i in sorted(scored)[:limit]]

    def node_label(self, node: int | None) -> str:
        return "" if node is None else self.model.graph.names[node]
