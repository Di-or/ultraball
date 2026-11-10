from sqlalchemy import ColumnElement, and_

from app.catalog.energy import not_basic_energy_clause
from app.catalog.models import Card


def corpus_clause(card: type[Card]) -> ColumnElement[bool]:
    """The printings that make up card entities: what enrichment tags and search returns.

    Everything stored except Basic Energy, which lives in the tray (CONTEXT.md: Basic-Energy tray),
    and textless printings, whose name-only `dedupe_key` isn't a real card (CONTEXT.md: Textless
    printing). `card` is the `cards` table or an alias of it.
    """
    return and_(not_basic_energy_clause(card.category, card.energy_type), card.is_textless.is_(False))
