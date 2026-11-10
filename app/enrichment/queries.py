from sqlalchemy import ColumnElement, and_, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.corpus import corpus_clause
from app.catalog.models import Card
from app.enrichment import status
from app.enrichment.models import CardEnrichment
from app.enrichment.taxonomy import PROMPT_VERSION, TAXONOMY_VERSION

# Statuses that mean "leave this dedupe_key alone" for the current version stamp:
# already in flight, already done, or parked for human repair. FAILED is
# deliberately excluded so a failed batch is retried on the next submit.
_SETTLED_STATUSES = (status.PENDING, status.COMPLETED, status.NEEDS_REPAIR)


def has_version_stamp(
    *, taxonomy_version: str = TAXONOMY_VERSION, prompt_version: str = PROMPT_VERSION
) -> ColumnElement[bool]:
    """A card_enrichment row carries this version stamp — the current one by default
    (CONTEXT.md: Enrichment identity)."""
    return and_(CardEnrichment.taxonomy_version == taxonomy_version, CardEnrichment.prompt_version == prompt_version)


async def get_cards_pending_enrichment(
    session: AsyncSession, *, taxonomy_version: str, prompt_version: str, repair_only: bool = False
) -> list[tuple[str, str]]:
    """(dedupe_key, canonical_card_text) pairs due a (re)enrichment Batch call.

    A dedupe_key is due when it has no card_enrichment row yet, its stored
    version stamp doesn't match the one passed in (a taxonomy/prompt bump), or
    its last attempt failed. Rows already `pending` or `needs_repair` are left
    alone — resubmitting an in-flight batch or an unresolved repair case would
    defeat resumability (CONTEXT.md: Enrichment identity).

    With `repair_only`, the due cards are exactly the `needs_repair` ones instead:
    the deliberate repair re-run, which leaves every other card for the ordinary submit.
    """
    latest_text = (
        select(Card.dedupe_key, Card.canonical_card_text)
        # Not Basic Energy (it lives in the tray) nor textless printings (no card entity yet).
        .where(corpus_clause(Card))
        .distinct(Card.dedupe_key)
        .order_by(Card.dedupe_key, Card.release_date.desc())
        .subquery()
    )

    if repair_only:
        needs_repair = select(CardEnrichment.dedupe_key).where(CardEnrichment.status == status.NEEDS_REPAIR)
        due = latest_text.c.dedupe_key.in_(needs_repair)
    else:
        settled = select(CardEnrichment.dedupe_key).where(
            has_version_stamp(taxonomy_version=taxonomy_version, prompt_version=prompt_version),
            CardEnrichment.status.in_(_SETTLED_STATUSES),
        )
        due = not_(latest_text.c.dedupe_key.in_(settled))

    stmt = select(latest_text.c.dedupe_key, latest_text.c.canonical_card_text).where(due)

    result = await session.execute(stmt)
    return [(row.dedupe_key, row.canonical_card_text) for row in result]


def _has_normalized_description() -> ColumnElement[bool]:
    """A normalized_description the embedding provider will accept: not NULL and not blank."""
    return func.btrim(CardEnrichment.normalized_description) != ""


async def get_cards_pending_embedding(session: AsyncSession) -> list[tuple[str, str]]:
    """(dedupe_key, normalized_description) pairs that have a description but no vector yet.

    Decoupled from the tagging pass's own resumability bookkeeping (status,
    batch_id, version stamps): any row with a non-blank description and no vector
    is eligible, so this runs and resumes independently of #21. A blank
    description is left out because the embedding provider rejects it, and one
    such text would fail the whole request it rides in.
    """
    stmt = (
        select(CardEnrichment.dedupe_key, CardEnrichment.normalized_description)
        .where(_has_normalized_description(), CardEnrichment.vector.is_(None))
        .order_by(CardEnrichment.dedupe_key)
    )

    result = await session.execute(stmt)
    return [(row.dedupe_key, row.normalized_description) for row in result]


async def count_cards_unembeddable(session: AsyncSession) -> int:
    """Rows with no vector that the embedding pass can't embed: no description, or a blank one.

    These are the cards waiting on (re)tagging — pending, failed or needs_repair.
    """
    stmt = select(func.count()).where(
        CardEnrichment.vector.is_(None),
        or_(CardEnrichment.normalized_description.is_(None), not_(_has_normalized_description())),
    )
    return await session.scalar(stmt) or 0
