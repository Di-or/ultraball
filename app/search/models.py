from typing import Literal

from pydantic import BaseModel, Field

from app.catalog.models import Card

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 30


class IntRange(BaseModel):
    """An inclusive `{gte, lte}` numeric range; either bound may be omitted."""

    gte: int | None = None
    lte: int | None = None


class Filters(BaseModel):
    """The closed candidate-pool gate zone (CONTEXT.md: Candidate pool).

    Fields conjoin (AND); a multi-valued field (`types`, `sub_category`)
    disjoins (OR/overlap) within itself.
    """

    format: Literal["standard"] | None = "standard"
    category: Literal["Pokemon", "Trainer", "Energy"] | None = None
    sub_category: list[Literal["ex", "mega", "ace-spec"]] | None = None
    types: list[str] | None = None
    hp: IntRange | None = None
    retreat: IntRange | None = None
    attack_cost: IntRange | None = None
    stage: Literal["Basic", "Stage 1", "Stage 2"] | None = None
    trainer_type: Literal["Item", "Supporter", "Stadium", "Tool"] | None = None
    energy_type: str | None = None
    set_id: str | None = None


class Facets(BaseModel):
    """UI-only facets (CONTEXT.md: Filter panel) — not part of the parse schema."""

    regulation_mark: list[str] | None = None
    rarity: list[str] | None = None


class SearchRequest(BaseModel):
    filters: Filters = Field(default_factory=Filters)
    facets: Facets = Field(default_factory=Facets)
    limit: int = Field(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT)
    offset: int = Field(default=0, ge=0)


class SearchResult(BaseModel):
    """One representative printing in the gated set (CONTEXT.md: Representative printing)."""

    model_config = {"from_attributes": True}

    entity_id: str
    printing_id: str
    name: str
    category: str
    hp: int | None
    types: list[str]
    stage: str | None
    sub_category: list[str]
    regulation_mark: str | None
    rarity: str | None
    set_id: str
    is_standard_legal: bool

    @classmethod
    def from_card(cls, card: Card) -> "SearchResult":
        return cls(
            entity_id=card.dedupe_key,
            printing_id=card.id,
            name=card.name,
            category=card.category,
            hp=card.hp,
            types=card.types,
            stage=card.stage,
            sub_category=card.sub_category,
            regulation_mark=card.regulation_mark,
            rarity=card.rarity,
            set_id=card.set_id,
            is_standard_legal=card.is_standard_legal,
        )


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    limit: int
    offset: int
