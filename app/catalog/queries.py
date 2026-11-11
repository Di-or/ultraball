from collections.abc import Collection

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.energy import basic_energy_clause
from app.catalog.models import Card
from app.catalog.representative import representative_order
from app.catalog.set_models import CatalogSet, SetSummary


async def get_representative_printing(session: AsyncSession, dedupe_key: str) -> Card | None:
    """The representative printing for a dedupe_key (CONTEXT.md: Representative printing)."""
    stmt = select(Card).where(Card.dedupe_key == dedupe_key).order_by(*representative_order(Card)).limit(1)
    return await session.scalar(stmt)


async def get_printings(session: AsyncSession, dedupe_key: str) -> list[Card]:
    """Every printing of a card entity, representative first (docs/archive/mvp-spec.md §12.4:
    Card-detail view; CONTEXT.md: Representative printing)."""
    stmt = select(Card).where(Card.dedupe_key == dedupe_key).order_by(*representative_order(Card))
    return list(await session.scalars(stmt))


async def get_cards_by_ids(session: AsyncSession, printing_ids: Collection[str]) -> list[Card]:
    """Printings by id, for resolving a deck's `printing_id` entries (`POST /decks/validate`)."""
    if not printing_ids:
        return []
    stmt = select(Card).where(Card.id.in_(printing_ids))
    return list(await session.scalars(stmt))


async def get_card_by_set_code_and_local_id(
    session: AsyncSession, set_code: str, local_id: str
) -> Card | None:
    """The printing a PTCGL line's `{set_code} {local_id}` tail identifies (issue #28)."""
    stmt = select(Card).where(Card.set_code == set_code.upper(), Card.local_id == local_id)
    return await session.scalar(stmt)


async def get_basic_energy_palette(session: AsyncSession) -> list[Card]:
    """The fixed basic-Energy palette for the tray, one representative printing per type
    (CONTEXT.md: Basic-Energy tray)."""
    stmt = (
        select(Card)
        .where(basic_energy_clause(Card.category, Card.energy_type))
        .order_by(*representative_order(Card))
    )
    seen: set[str] = set()
    palette: list[Card] = []
    for card in await session.scalars(stmt):
        if card.dedupe_key not in seen:
            seen.add(card.dedupe_key)
            palette.append(card)
    return palette


async def get_sets(session: AsyncSession) -> list[SetSummary]:
    """Every distinct set in the catalog, newest first (feeds the Filter panel's set dropdown)."""
    stmt = (
        select(
            Card.set_id,
            Card.set_code,
            # max(): rows backfilled with '' (from before `set_name`) mustn't split a set in two.
            func.max(Card.set_name).label("set_name"),
            func.max(Card.release_date).label("release_date"),
        )
        .group_by(Card.set_id, Card.set_code)
        .order_by(func.max(Card.release_date).desc(), Card.set_id)
    )
    return [
        SetSummary(id=row.set_id, code=row.set_code, name=row.set_name, release_date=row.release_date)
        for row in await session.execute(stmt)
    ]


async def get_set_list(session: AsyncSession) -> tuple[CatalogSet, ...]:
    """The catalog's set list for the parse model (issue #90); `render_set_lines` fixes its order."""
    return tuple(CatalogSet(id=s.id, code=s.code, name=s.name) for s in await get_sets(session))
