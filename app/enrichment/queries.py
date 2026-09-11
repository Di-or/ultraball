from sqlalchemy import not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Card
from app.enrichment import status
from app.enrichment.models import CardEnrichment

# Statuses that mean "leave this dedupe_key alone" for the current version stamp:
# already in flight, already done, or parked for human repair. FAILED is
# deliberately excluded so a failed batch is retried on the next submit.
_SETTLED_STATUSES = (status.PENDING, status.COMPLETED, status.NEEDS_REPAIR)


async def get_cards_pending_enrichment(
    session: AsyncSession, *, taxonomy_version: str, prompt_version: str
) -> list[tuple[str, str]]:
    """(dedupe_key, canonical_card_text) pairs due a (re)enrichment Batch call.

    A dedupe_key is due when it has no card_enrichment row yet, its stored
    version stamp doesn't match the one passed in (a taxonomy/prompt bump), or
    its last attempt failed. Rows already `pending` or `needs_repair` are left
    alone — resubmitting an in-flight batch or an unresolved repair case would
    defeat resumability (CONTEXT.md: Enrichment identity).
    """
    latest_text = (
        select(Card.dedupe_key, Card.canonical_card_text)
        .distinct(Card.dedupe_key)
        .order_by(Card.dedupe_key, Card.release_date.desc())
        .subquery()
    )

    settled = select(CardEnrichment.dedupe_key).where(
        CardEnrichment.taxonomy_version == taxonomy_version,
        CardEnrichment.prompt_version == prompt_version,
        CardEnrichment.status.in_(_SETTLED_STATUSES),
    )

    stmt = select(latest_text.c.dedupe_key, latest_text.c.canonical_card_text).where(
        not_(latest_text.c.dedupe_key.in_(settled))
    )

    result = await session.execute(stmt)
    return [(row.dedupe_key, row.canonical_card_text) for row in result]


async def get_cards_pending_embedding(session: AsyncSession) -> list[tuple[str, str]]:
    """(dedupe_key, normalized_description) pairs that have a description but no vector yet.

    Decoupled from the tagging pass's own resumability bookkeeping (status,
    batch_id, version stamps): any row with a description and no vector is
    eligible, so this runs and resumes independently of #21.
    """
    stmt = select(CardEnrichment.dedupe_key, CardEnrichment.normalized_description).where(
        CardEnrichment.normalized_description.is_not(None),
        CardEnrichment.vector.is_(None),
    )

    result = await session.execute(stmt)
    return [(row.dedupe_key, row.normalized_description) for row in result]
