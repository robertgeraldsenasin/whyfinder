"""The facts behind one explanation, in the form generation and the checker use (06_RAG step 1-3).

`facts` turns the served model's exact explanation (attributions, counterfactual, graph paths, the
variety flag) and the review quotes retrieved for the pick into a `Pack` for the prompt and a
`Source` for the checker. The API and `whyfinder rag eval` both build their explanations here.
"""

from __future__ import annotations

import numpy as np

from whyfinder.rag.claims import Source
from whyfinder.rag.generate import Pack
from whyfinder.serve.model import Explanation, ServedModel

QUOTES = 2


def quotes(model: ServedModel, pick: int, source: int) -> list[tuple[str, str, str]]:
    """For each aspect the pick shares with a liked game, the best review of the pick that names it
    (BM25 must match, so the quote really mentions the aspect); distinct quotes, at most two."""
    if model.reviews is None:
        return []
    index = model.reviews
    out: list[tuple[str, str, str]] = []
    used: set[int] = set()
    for aspect in model.aspects(pick, source):
        hits = index.search(aspect, 5, game=pick)
        hit = next((h for h in hits if h.bm25_rank is not None and h.chunk not in used), None)
        if hit is None:
            continue
        used.add(hit.chunk)
        chunk = index.chunks[hit.chunk]
        out.append((chunk.chunk_id, aspect, chunk.text))
        if len(out) == QUOTES:
            break
    return out


def path_text(model: ServedModel, kind: str, via: int | None, source: int) -> str:
    other = model.title(source)
    if kind == "co-play" or via is None:
        return f"is played by many of the same players as {other}"
    return f"shares the {kind} {model.node_label(via)} with {other}"


def facts(
    model: ServedModel, history: list[tuple[int, float]], e: Explanation
) -> tuple[Pack, Source]:
    """The pack for the prompt and the source for the checker, for one explained pick."""
    total = sum(abs(c.total) for c in e.contributions) or 1.0
    attributions = tuple(
        (str(model.ids[c.game]), model.title(c.game), c.total / total) for c in e.contributions
    )
    top = next((c.game for c in e.contributions if c.total > 0), None)
    found = quotes(model, e.pick, top) if top is not None else []
    removed = tuple((str(model.ids[j]), model.title(j)) for j in e.counterfactual.removed)
    pack = Pack(
        pick_title=model.title(e.pick),
        liked=tuple((str(model.ids[j]), model.title(j)) for j, _ in history),
        attributions=attributions,
        removed=removed,
        paths=tuple(path_text(model, p.kind, p.via, p.source) for p in e.paths[:2]),
        kept_for_variety=e.kept_for_variety,
        quotes=tuple(found),
    )
    chunks: dict[str, str] = {}
    if model.reviews is not None:
        index = model.reviews
        for i in index.by_game.get(e.pick, []):
            chunks[index.chunks[int(i)].chunk_id] = index.chunks[int(i)].text
    source = Source(
        pick_title=pack.pick_title,
        attributions={gid: (title, share) for gid, title, share in attributions},
        chunks=chunks,
        removed=frozenset(gid for gid, _ in removed),
        catalogue=tuple(model.title(i) for i in range(len(model.ids))),
    )
    return pack, source


def sample(
    model: ServedModel, n: int, *, size: int = 6, seed: int
) -> list[tuple[list[tuple[int, float]], Explanation]]:
    """`n` evaluation cases: a seeded random history of `size` catalogue games and its top pick."""
    from whyfinder.serve.model import Filters

    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        chosen = sorted(int(i) for i in rng.choice(len(model.ids), size=size, replace=False))
        history = [(i, model.weight) for i in chosen]
        rec = model.run(history, k=int(model.p["k"]), filters=Filters(), diversity=True)
        if not rec.picks:
            continue
        out.append((history, model.explain(history, rec.picks[0], filters=Filters())))
    return out
