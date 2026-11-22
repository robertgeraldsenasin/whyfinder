"""The REST API (FR-21; docs/spec/12_API.md).

Endpoints: POST /recommend, POST /explain, GET /search, GET /healthz, GET /version. Errors are
`application/problem+json` (RFC 9457). Bodies are limited to 16 KB, and each client IP to 30
requests a minute on /explain and 120 on the rest (fixed one-minute windows).

Explanations are sentences about the exact attributions, the counterfactual and review quotes. By
default they are the template sentences; with an Ollama model configured, the model writes them
from the same facts. Either way every claim passes the checker before it is returned (06_RAG).

Browsers may call the API from the origins in `ORIGINS` (or WHYFINDER_CORS_ORIGINS), so the demo
can use a copy running on the visitor's own machine.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Annotated, Any, Literal, cast

from fastapi import FastAPI, Query
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from whyfinder import __version__
from whyfinder.rag import claims as rc
from whyfinder.rag.generate import (
    Backend,
    CacheMissError,
    LlmUnavailableError,
    template,
)
from whyfinder.rag.generate import explain as generate
from whyfinder.serve import grounding
from whyfinder.serve import schemas as s
from whyfinder.serve.model import MODEL_VERSION, Filters, ServedModel
from whyfinder.serve.query import parse_query

MAX_BODY = 16 * 1024
LIMITS = {"explain": 30, "default": 120}
PROBLEM = "application/problem+json"
History = list[tuple[int, float]]


def problem(
    status: int,
    title: str,
    detail: str,
    *,
    headers: Mapping[str, str] | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
    }
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM, headers=headers)


class RateLimiter:
    """Fixed one-minute windows per (client, group); `clock` is injectable for tests."""

    def __init__(self, limits: dict[str, int], clock: Callable[[], float] = time.monotonic) -> None:
        self.limits = limits
        self.clock = clock
        self.minute = -1
        self.counts: dict[tuple[str, str], int] = {}

    def allow(self, client: str, group: str) -> bool:
        minute = int(self.clock() // 60)
        if minute != self.minute:
            self.minute, self.counts = minute, {}
        used = self.counts.get((client, group), 0)
        if used >= self.limits.get(group, self.limits["default"]):
            return False
        self.counts[(client, group)] = used + 1
        return True


ORIGINS = (
    "https://robertgeraldsenasin.github.io",
    "http://localhost:5173",
    "http://localhost:4173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:4173",
)


def origins(env: Mapping[str, str]) -> tuple[str, ...]:
    """Origins allowed to call the API from a browser: WHYFINDER_CORS_ORIGINS, comma-separated
    (empty turns cross-origin calls off), else the demo's own origins."""
    raw = env.get("WHYFINDER_CORS_ORIGINS")
    if raw is None:
        return ORIGINS
    return tuple(o.strip().rstrip("/") for o in raw.split(",") if o.strip())


class Guard:
    """Rate limit, then refuse bodies over MAX_BODY before the app parses them."""

    def __init__(self, app: ASGIApp, limiter: RateLimiter) -> None:
        self.app = app
        self.limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        group = "explain" if scope["path"].rstrip("/") == "/explain" else "default"
        client = scope["client"][0] if scope.get("client") else "unknown"
        if not self.limiter.allow(client, group):
            limit = self.limiter.limits.get(group, self.limiter.limits["default"])
            await problem(
                429,
                "Too many requests",
                f"{limit} requests a minute on this endpoint",
                headers={"Retry-After": "60"},
            )(scope, receive, send)
            return
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > MAX_BODY:
                too_big = f"bodies are limited to {MAX_BODY} bytes"
                await problem(413, "Request too large", too_big)(scope, receive, send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        sent = False

        async def replay() -> Message:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def to_api(claim: rc.Claim) -> s.Claim:
    evidence: list[s.Evidence] = []
    for e in claim.evidence:
        if isinstance(e, rc.AttributionRef):
            evidence.append(
                s.AttributionEvidence(type="attribution", game_id=e.game_id, share=e.share)
            )
        elif isinstance(e, rc.ReviewRef):
            evidence.append(s.ReviewEvidence(type="review", chunk_id=e.chunk_id, quote=e.quote))
        else:
            evidence.append(
                s.CounterfactualEvidence(
                    type="counterfactual", removed_game_ids=list(e.removed_game_ids)
                )
            )
    return s.Claim(text=claim.text, evidence=evidence)


def to_rag(claim: s.Claim) -> rc.Claim:
    evidence: list[rc.Evidence] = []
    for e in claim.evidence:
        if isinstance(e, s.ReviewEvidence):
            evidence.append(rc.ReviewRef(e.chunk_id, e.quote))
        elif isinstance(e, s.CounterfactualEvidence):
            evidence.append(rc.CounterfactualRef(tuple(e.removed_game_ids)))
        else:
            evidence.append(rc.AttributionRef(e.game_id, e.share))
    return rc.Claim(claim.text, tuple(evidence))


def check_claims(claims: list[s.Claim], source: rc.Source) -> list[str]:
    """FR-17 on the API's claims (`rag.claims.check`)."""
    return rc.check([to_rag(c) for c in claims], source)


Responses = dict[int | str, dict[str, Any]]
ERRORS: Responses = {
    400: {"description": "The body is not valid JSON"},
    404: {"description": "None of the liked games, or the game asked about, is in the catalogue"},
    413: {"description": "The body is over 16 KB"},
    422: {"description": "The request does not match the schema"},
    429: {"description": "Too many requests from this client in the current minute"},
}
EXPLAIN_ERRORS: Responses = {
    **ERRORS,
    409: {"description": "The game to explain is one of the liked games"},
}
SMALL_ERRORS: Responses = {k: v for k, v in ERRORS.items() if k in (413, 422, 429)}
RATE_ERRORS: Responses = {k: v for k, v in ERRORS.items() if k == 429}
REVIEW_ERRORS: Responses = {
    **SMALL_ERRORS,
    404: {"description": "The game is not in the catalogue"},
    503: {"description": "This server was started without the review index"},
}


def problem_openapi(app: FastAPI) -> dict[str, Any]:
    """FastAPI's document, with every 4xx and 5xx response typed as a Problem in problem+json."""
    if app.openapi_schema:
        return app.openapi_schema
    doc = get_openapi(
        title=app.title, version=app.version, description=app.description, routes=app.routes
    )
    ref = {"$ref": "#/components/schemas/Problem"}
    for operations in doc["paths"].values():
        for operation in operations.values():
            for code, response in operation["responses"].items():
                if code.startswith(("4", "5")):
                    response["content"] = {PROBLEM: {"schema": ref}}
    schemas = doc.setdefault("components", {}).setdefault("schemas", {})
    for name in ("HTTPValidationError", "ValidationError"):
        schemas.pop(name, None)
    problem_schema = s.Problem.model_json_schema(ref_template="#/components/schemas/{model}")
    schemas.update(problem_schema.pop("$defs", {}))
    schemas["Problem"] = problem_schema
    app.openapi_schema = doc
    return doc


def create_app(
    model: ServedModel,
    *,
    git_sha: str | None = None,
    limiter: RateLimiter | None = None,
    llm: Backend | None = None,
    cors: Sequence[str] = (),
) -> FastAPI:
    """The API over a served model. With `llm`, explanations are generated by that model, checked,
    retried once and otherwise replaced by the template sentences (06_RAG). Browsers on the `cors`
    origins may call it, a public page calling a copy on the visitor's own machine included
    (Private Network Access); preflights never reach the rate limiter."""
    app = FastAPI(
        title="Whyfinder API",
        version=__version__,
        description="Explainable Steam game recommendations: every pick with its exact reasons.",
    )
    app.openapi = lambda: problem_openapi(app)  # type: ignore[method-assign]
    app.add_middleware(Guard, limiter=limiter or RateLimiter(LIMITS))
    if cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors),
            allow_methods=["GET", "POST"],
            allow_headers=["content-type"],
            allow_private_network=True,
            max_age=600,
        )
    sha = git_sha or os.environ.get("WHYFINDER_GIT_SHA", "unknown")
    seed = int(model.p.get("seed", 0))

    @app.exception_handler(HTTPException)
    async def http_problem(_: Request, exc: HTTPException) -> JSONResponse:
        titles = {
            400: "Bad request",
            404: "Not found",
            405: "Method not allowed",
            409: "Conflict",
            503: "Unavailable",
        }
        title = titles.get(exc.status_code, "Request failed")
        return problem(exc.status_code, title, str(exc.detail), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": [str(x) for x in e.get("loc", ())], "msg": str(e.get("msg", ""))}
            for e in exc.errors()
        ]
        detail = "the request does not match the schema"
        return problem(422, "Invalid request", detail, errors=errors)

    def taste(body: s.Liked) -> tuple[History, list[str], list[str], Filters]:
        ids = [int(g) for g in body.liked_game_ids]
        unresolved: list[str] = []
        f = body.filters
        tags, max_price, year_min, year_max = list(f.tags), f.max_price, f.year_min, f.year_max
        if body.query:
            q = parse_query(body.query, model.games)
            ids += [model.ids[i] for i in q.anchors]
            unresolved = q.unresolved
            tags += [t for t in q.tags if t not in tags]
            max_price = q.max_price if q.max_price is not None else max_price
            year_min = q.year_min if q.year_min is not None else year_min
            year_max = q.year_max if q.year_max is not None else year_max
        history, unknown = model.history(ids)
        if not history:
            raise HTTPException(404, "none of these games is in the catalogue this model serves")
        filters = Filters(tuple(tags), max_price, year_min, year_max)
        return history, [str(u) for u in unknown], unresolved, filters

    def attribution_rows(history: History, pick: int) -> list[s.Attribution]:
        parts = model.contributions(history, pick)
        total = sum(abs(c.total) for c in parts) or 1.0
        return [
            s.Attribution(
                game_id=str(model.ids[c.game]),
                title=model.title(c.game),
                contribution=c.total,
                share=c.total / total,
                ease_part=c.ease,
                ppr_part=c.ppr,
            )
            for c in parts
        ]

    @app.post("/recommend", response_model=s.RecommendOut, responses=ERRORS)
    def recommend(body: s.RecommendIn) -> s.RecommendOut:
        """Up to k picks for a taste, each with its largest reason."""
        history, unknown, unresolved, filters = taste(body)
        rec = model.run(history, k=body.k, filters=filters, diversity=body.diversity)
        items = []
        for rank, pick in enumerate(rec.picks):
            top = next((r for r in attribution_rows(history, pick) if r.contribution > 0), None)
            reason = (
                s.Reason(game_id=top.game_id, title=top.title, share=top.share) if top else None
            )
            items.append(
                s.Item(
                    game_id=str(model.ids[pick]),
                    title=model.title(pick),
                    score=float(rec.scores[pick]),
                    rank=rank + 1,
                    kept_for_variety=rec.variety[rank],
                    top_reason=reason,
                )
            )
        return s.RecommendOut(
            items=items,
            liked_game_ids=[str(model.ids[j]) for j, _ in history],
            unknown_game_ids=unknown,
            unresolved_terms=unresolved,
            model_version=MODEL_VERSION,
        )

    @app.post("/explain", response_model=s.ExplainOut, responses=EXPLAIN_ERRORS)
    def explain(body: s.ExplainIn) -> s.ExplainOut:
        """Why a game is (or is not) picked: exact attributions, a counterfactual and paths."""
        history, _, _, filters = taste(body)
        pick = model.index.get(int(body.game_id))
        if pick is None:
            raise HTTPException(404, f"game {body.game_id} is not in the catalogue")
        if any(j == pick for j, _ in history):
            raise HTTPException(409, "the game to explain is one of the liked games")
        e = model.explain(history, pick, filters=filters)
        rows = attribution_rows(history, pick)
        pack, source = grounding.facts(model, history, e)
        rejected: list[str] = []
        if llm is None:
            final, fallback = template(pack), True
        else:
            try:
                outcome = generate(pack, source, llm, lambda: template(pack), seed=seed)
                final, fallback = outcome.claims, outcome.fallback_used
                rejected = [r for a in outcome.attempts for r in a.reasons]
            except (LlmUnavailableError, CacheMissError) as exc:
                final, fallback, rejected = template(pack), True, [f"llm unavailable: {exc}"]
        claims = [to_api(c) for c in final]
        reasons = check_claims(claims, source)
        return s.ExplainOut(
            game_id=str(model.ids[pick]),
            title=model.title(pick),
            score=e.score,
            rank=None if e.rank is None else e.rank + 1,
            attributions=rows,
            counterfactual=s.CounterfactualOut(
                removed_game_ids=[str(model.ids[j]) for j in e.counterfactual.removed],
                guarantee="irreducible" if e.rank is not None else "not_in_picks",
                pipeline_runs=e.counterfactual.runs,
            ),
            paths=[
                s.PathOut(
                    via=cast(s.PathKind, p.kind),
                    label=model.node_label(p.via) if p.via is not None else model.title(p.source),
                    from_game_id=str(model.ids[p.source]),
                    weight=p.weight,
                )
                for p in e.paths
            ],
            kept_for_variety=e.kept_for_variety,
            claims=claims,
            checker=s.Checker(
                passed=not reasons, fallback_used=fallback, reasons=reasons or rejected
            ),
            model_version=MODEL_VERSION,
        )

    @app.get("/search", response_model=s.SearchOut, responses=SMALL_ERRORS)
    def search(q: Annotated[str, Query(min_length=1, max_length=100)]) -> s.SearchOut:
        """Up to ten catalogue titles: those starting with q, then those containing it."""
        hits = [
            s.SearchHit(
                game_id=str(model.ids[i]), title=model.title(i), year=model.games[i].get("year")
            )
            for i in model.search(q)
        ]
        return s.SearchOut(items=hits)

    @app.get("/reviews", response_model=s.ReviewsOut, responses=REVIEW_ERRORS)
    def reviews(
        q: Annotated[str, Query(min_length=1, max_length=200)],
        game_id: Annotated[str | None, Query(pattern=r"^[0-9]{1,10}$")] = None,
        k: Annotated[int, Query(ge=1, le=20)] = 5,
    ) -> s.ReviewsOut:
        """Review sentences for a query (BM25 and LSA vectors in HNSW, fused by RRF), optionally
        from one game's reviews only."""
        if model.reviews is None:
            raise HTTPException(503, "the review index is not built on this server")
        game = None
        if game_id is not None:
            game = model.index.get(int(game_id))
            if game is None:
                raise HTTPException(404, f"game {game_id} is not in the catalogue")
        items = []
        for h in model.reviews.search(q, k, game=game):
            c = model.reviews.chunks[h.chunk]
            items.append(
                s.ReviewHit(
                    chunk_id=c.chunk_id,
                    game_id=str(model.ids[c.game]),
                    title=model.title(c.game),
                    text=c.text,
                    hours=c.hours,
                    year=c.year,
                    score=h.score,
                    bm25_rank=h.bm25_rank,
                    dense_rank=h.dense_rank,
                )
            )
        return s.ReviewsOut(items=items)

    @app.get("/healthz", response_model=s.Health, responses=RATE_ERRORS)
    def health() -> s.Health:
        """The model is loaded; the review index is built if the server was given reviews; the LLM
        is off, ok or down (then explanations fall back to the template sentences)."""
        index: Literal["ok", "not_built"] = "ok" if model.reviews is not None else "not_built"
        if llm is None:
            return s.Health(status="ok", artifacts="ok", index=index, llm="off")
        try:
            _ = llm.digest
        except LlmUnavailableError:
            return s.Health(status="degraded", artifacts="ok", index=index, llm="down")
        return s.Health(status="ok", artifacts="ok", index=index, llm="ok")

    @app.get("/version", response_model=s.Version, responses=RATE_ERRORS)
    def version() -> s.Version:
        """What is serving: the commit, the model, the data and the hashes of its files."""
        return s.Version(
            git_sha=sha,
            model_version=MODEL_VERSION,
            data_version=model.data_version,
            artifacts=model.hashes,
        )

    return app
