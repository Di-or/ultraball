from typing import Literal

from pydantic import BaseModel, Field

from app.catalog.deck_validation import LegalityReport


class DeckEntry(BaseModel):
    """One line of a submitted deck (docs/archive/mvp-spec.md §14: `POST /decks/validate`)."""

    printing_id: str
    count: int


class DeckValidateRequest(BaseModel):
    """The submitted deck (docs/archive/mvp-spec.md §14: `POST /decks/validate`)."""

    entries: list[DeckEntry] = Field(default_factory=list)
    format: Literal["standard"] = "standard"


class Violation(BaseModel):
    """One flagged rule breach (docs/archive/mvp-spec.md §12.3) — allow-and-flag, never blocking."""

    model_config = {"from_attributes": True}

    code: str
    message: str
    cards: list[str] = Field(default_factory=list)


class Counts(BaseModel):
    """P/T/E tallies plus the total, riding in the same report (docs/archive/mvp-spec.md §12.3)."""

    model_config = {"from_attributes": True}

    pokemon: int
    trainer: int
    energy: int
    total: int


class DeckValidateResponse(BaseModel):
    """The legality report (CONTEXT.md: Deck panel) — the client's single source of truth."""

    legal: bool
    counts: Counts
    violations: list[Violation]

    @classmethod
    def from_report(cls, report: LegalityReport) -> "DeckValidateResponse":
        return cls(
            legal=report.legal,
            counts=Counts.model_validate(report.counts),
            violations=[Violation.model_validate(v) for v in report.violations],
        )
