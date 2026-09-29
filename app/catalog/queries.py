from collections.abc import Collection

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Card
from app.catalog.set_models import SetSummary


async def get_representative_printing(session: AsyncSession, dedupe_key: str) -> Card | None:
    """The most-recent printing for a dedupe_key (CONTEXT.md: representative printing).

    Most-recent is authoritative: regulation marks advance monotonically, so the
    newest printing carries the newest legality and the best image. Ties on
    release_date (rare — same-day releases across sets) break on ingest recency
    rather than `id`, since TCGdex ids aren't zero-padded and don't sort
    lexicographically by set recency (e.g. "swsh12-1" < "swsh2-1").
    """
    stmt = (
        select(Card)
        .where(Card.dedupe_key == dedupe_key)
        .order_by(Card.release_date.desc(), Card.ingested_at.desc())
        .limit(1)
    )
    return await session.scalar(stmt)


async def get_printings(session: AsyncSession, dedupe_key: str) -> list[Card]:
    """Every printing of a card entity, newest first (docs/archive/mvp-spec.md §12.4: Card-detail view)."""
    stmt = (
        select(Card)
        .where(Card.dedupe_key == dedupe_key)
        .order_by(Card.release_date.desc(), Card.ingested_at.desc())
    )
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


async def get_sets(session: AsyncSession) -> list[SetSummary]:
    """Every distinct set, newest first. Derived from `cards` — there is no sets table."""
    release_date = func.min(Card.release_date)
    stmt = (
        select(Card.set_id, func.min(Card.set_code), release_date)
        .group_by(Card.set_id)
        .order_by(release_date.desc(), Card.set_id)
    )
    return [
        SetSummary(id=set_id, code=code, release_date=released)
        for set_id, code, released in await session.execute(stmt)
    ]


async def get_basic_energy_palette(session: AsyncSession) -> list[Card]:
    """The fixed basic-Energy palette for the tray, one representative printing per type
    (CONTEXT.md: Basic-Energy tray)."""
    stmt = (
        select(Card)
        .where(Card.category == "Energy", Card.energy_type == "Basic")
        .order_by(Card.release_date.desc(), Card.ingested_at.desc())
    )
    seen: set[str] = set()
    palette: list[Card] = []
    for card in await session.scalars(stmt):
        if card.dedupe_key not in seen:
            seen.add(card.dedupe_key)
            palette.append(card)
    return palette
