from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.enrichment_client import EnrichmentClient, EnrichmentRequest
from app.enrichment import status
from app.enrichment.models import CardEnrichment
from app.enrichment.queries import get_cards_pending_enrichment
from app.enrichment.taxonomy import PROMPT_VERSION, TAXONOMY_VERSION
from app.enrichment.validation import validate_enrichment_result


async def submit_enrichment_batch(
    session: AsyncSession,
    enrichment_client: EnrichmentClient,
    *,
    taxonomy_version: str = TAXONOMY_VERSION,
    prompt_version: str = PROMPT_VERSION,
) -> str | None:
    """Submit one Batch call covering every dedupe_key currently due enrichment.

    Returns the new batch_id, or `None` if the corpus has nothing pending (an
    unchanged-corpus re-run is a no-op). Rows are staked out as `pending` under
    that batch_id before this returns, so a crash right after submission still
    resumes cleanly via `poll_and_apply_batch`.
    """
    pending = await get_cards_pending_enrichment(
        session, taxonomy_version=taxonomy_version, prompt_version=prompt_version
    )
    if not pending:
        return None

    requests = [
        EnrichmentRequest(dedupe_key=dedupe_key, canonical_card_text=canonical_card_text)
        for dedupe_key, canonical_card_text in pending
    ]
    batch_id = await enrichment_client.submit_batch(requests)

    for dedupe_key, _ in pending:
        values = {
            "dedupe_key": dedupe_key,
            "normalized_description": None,
            "tags": [],
            "suggested_new_tag": None,
            "rationale": None,
            "taxonomy_version": taxonomy_version,
            "prompt_version": prompt_version,
            "status": status.PENDING,
            "batch_id": batch_id,
        }
        await session.execute(
            insert(CardEnrichment)
            .values(**values)
            .on_conflict_do_update(index_elements=[CardEnrichment.dedupe_key], set_=values)
        )

    await session.commit()
    return batch_id


async def poll_and_apply_batch(
    session: AsyncSession,
    enrichment_client: EnrichmentClient,
    batch_id: str,
    *,
    taxonomy_version: str = TAXONOMY_VERSION,
    prompt_version: str = PROMPT_VERSION,
) -> str:
    """Advance one in-flight batch: apply results once the Batch job is done.

    Safe to call repeatedly (e.g. on a schedule) — a still-pending batch is a
    no-op, so resuming after a crash mid-run just means polling again. Postgres
    validates NOT NULL columns on the INSERT branch of `ON CONFLICT DO UPDATE`
    even though the row here always already exists (staked out by
    `submit_enrichment_batch`), so the version stamp is passed through again.
    """
    batch_status = await enrichment_client.poll_batch(batch_id)

    if batch_status == status.PENDING:
        return batch_status

    if batch_status == status.FAILED:
        await session.execute(
            update(CardEnrichment).where(CardEnrichment.batch_id == batch_id).values(status=status.FAILED)
        )
        await session.commit()
        return batch_status

    results = await enrichment_client.fetch_results(batch_id)
    for result in results:
        validated = validate_enrichment_result(result)
        values = {
            "dedupe_key": result.dedupe_key,
            "normalized_description": result.normalized_description,
            "tags": validated.tags,
            "suggested_new_tag": result.suggested_new_tag,
            "rationale": result.rationale,
            "taxonomy_version": taxonomy_version,
            "prompt_version": prompt_version,
            "status": validated.status,
            "batch_id": batch_id,
        }
        await session.execute(
            insert(CardEnrichment)
            .values(**values)
            .on_conflict_do_update(index_elements=[CardEnrichment.dedupe_key], set_=values)
        )

    await session.commit()
    return batch_status
