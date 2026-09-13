from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Card


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
