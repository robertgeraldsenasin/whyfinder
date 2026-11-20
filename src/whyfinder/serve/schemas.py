"""Request and response models (docs/spec/12_API.md). Steam app IDs travel as strings.

Inputs are strict (no "2010" for a year, no 1 for true) so that what the OpenAPI schema rejects,
the server rejects too; the contract tests check both directions.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

AppId = str
GameId = Annotated[str, Field(pattern=r"^[0-9]{1,10}$", examples=["367520"])]


def _integral(value: object) -> object:
    """JSON Schema counts 2010.0 as an integer, so the strict models accept it as one."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


# Bounds go before the validator so the JSON schema states them as minimum and maximum.
Year = Annotated[int, Field(ge=1970, le=2100), BeforeValidator(_integral)]
Count = Annotated[int, Field(ge=1, le=20), BeforeValidator(_integral)]


class FiltersIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tags: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(
        default_factory=list, max_length=20
    )
    max_price: float | None = Field(default=None, ge=0)
    year_min: Year | None = None
    year_max: Year | None = None


# The schema states the rule the validator enforces: at least one liked game, or a query.
NEED_A_TASTE: dict[str, Any] = {
    "anyOf": [
        {"required": ["liked_game_ids"], "properties": {"liked_game_ids": {"minItems": 1}}},
        {"required": ["query"]},
    ]
}


class Liked(BaseModel):
    """A taste: liked games, a description, or both (the description's titles join the list)."""

    model_config = ConfigDict(extra="forbid", strict=True, json_schema_extra=NEED_A_TASTE)

    liked_game_ids: list[GameId] = Field(default_factory=list, max_length=50)
    query: str | None = Field(default=None, min_length=1, max_length=300)
    filters: FiltersIn = Field(default_factory=FiltersIn)

    @model_validator(mode="after")
    def need_a_taste(self) -> Liked:
        if not self.liked_game_ids and "query" not in self.model_fields_set:
            raise ValueError("give liked_game_ids or a query")
        return self


class RecommendIn(Liked):
    k: Count = 10
    diversity: bool = True


class Reason(BaseModel):
    game_id: AppId
    title: str
    share: float


class Item(BaseModel):
    game_id: AppId
    title: str
    score: float
    rank: int
    kept_for_variety: bool
    top_reason: Reason | None


class RecommendOut(BaseModel):
    items: list[Item]
    liked_game_ids: list[AppId]
    unknown_game_ids: list[AppId]
    unresolved_terms: list[str]
    model_version: str


class ExplainIn(Liked):
    game_id: GameId


class Attribution(BaseModel):
    game_id: AppId
    title: str
    contribution: float
    share: float
    ease_part: float
    ppr_part: float


class CounterfactualOut(BaseModel):
    removed_game_ids: list[AppId]
    guarantee: Literal["irreducible", "exact_min", "not_in_picks"]
    pipeline_runs: int


PathKind = Literal["co-play", "tag", "developer", "publisher"]


class PathOut(BaseModel):
    via: PathKind
    label: str
    from_game_id: AppId
    weight: float


class AttributionEvidence(BaseModel):
    type: Literal["attribution"]
    game_id: AppId
    share: float


class ReviewEvidence(BaseModel):
    type: Literal["review"]
    chunk_id: str
    quote: str


class CounterfactualEvidence(BaseModel):
    type: Literal["counterfactual"]
    removed_game_ids: list[AppId]


Evidence = Annotated[
    AttributionEvidence | ReviewEvidence | CounterfactualEvidence, Field(discriminator="type")
]


class Claim(BaseModel):
    text: str
    evidence: list[Evidence]


class Checker(BaseModel):
    passed: bool
    fallback_used: bool
    reasons: list[str]


class ExplainOut(BaseModel):
    game_id: AppId
    title: str
    score: float
    rank: int | None
    attributions: list[Attribution]
    counterfactual: CounterfactualOut
    paths: list[PathOut]
    kept_for_variety: bool
    claims: list[Claim]
    checker: Checker
    model_version: str


class SearchHit(BaseModel):
    game_id: AppId
    title: str
    year: int | None


class SearchOut(BaseModel):
    items: list[SearchHit]


class ReviewHit(BaseModel):
    chunk_id: str
    game_id: AppId
    title: str
    text: str
    hours: float
    year: int | None
    score: float
    bm25_rank: int | None
    dense_rank: int | None


class ReviewsOut(BaseModel):
    items: list[ReviewHit]


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    artifacts: Literal["ok"]
    index: Literal["ok", "not_built"]
    llm: Literal["off", "ok", "down"]


class ProblemError(BaseModel):
    loc: list[str]
    msg: str


class Problem(BaseModel):
    """RFC 9457 problem details; `errors` lists what failed validation."""

    type: str
    title: str
    status: int
    detail: str
    errors: list[ProblemError] | None = None


class Version(BaseModel):
    git_sha: str
    model_version: str
    data_version: str
    artifacts: dict[str, str]
