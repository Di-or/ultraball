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
