from typing import Literal

from pydantic import BaseModel, Field

from app.catalog.deck_validation import LegalityReport


class DeckEntry(BaseModel):
    """One line of a submitted deck (docs/archive/mvp-spec.md §14: `POST /decks/validate`)."""

    printing_id: str
    count: int


class DeckValidateRequest(BaseModel):
    entries: list[DeckEntry] = Field(default_factory=list)
    format: Literal["standard"] = "standard"


class Violation(BaseModel):
    code: str
    message: str
    cards: list[str] = Field(default_factory=list)


class Counts(BaseModel):
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
            counts=Counts(
                pokemon=report.counts.pokemon,
                trainer=report.counts.trainer,
                energy=report.counts.energy,
                total=report.counts.total,
            ),
            violations=[
                Violation(code=v.code, message=v.message, cards=v.cards) for v in report.violations
            ],
        )
