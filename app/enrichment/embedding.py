from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.embedding_client import MAX_DOCUMENTS_PER_REQUEST, EmbeddingClient
from app.enrichment.models import CardEnrichment
from app.enrichment.queries import count_cards_unembeddable, get_cards_pending_embedding


@dataclass(frozen=True)
class EmbeddingPassReport:
    """What one embedding pass did.

    `embedded`: cards that got a vector on this pass.
    `skipped`: cards still without a vector because they have no usable description
    (pending, failed or needs_repair tagging), left for a later pass.
    """

    embedded: int
    skipped: int


async def run_embedding_pass(
    session: AsyncSession,
    embedding_client: EmbeddingClient,
    *,
    chunk_size: int = MAX_DOCUMENTS_PER_REQUEST,
    dedupe_keys: Collection[str] | None = None,
) -> EmbeddingPassReport:
    """Embed every dedupe_key that has a non-blank normalized_description but no vector yet.

    A decoupled step after tagging (#21): safe to call on its own and to
    repeat, since already-embedded rows drop out of `get_cards_pending_embedding`.
    Vectors are committed `chunk_size` cards at a time, so a provider failure
    part-way keeps every chunk already embedded and a re-run picks up the rest.
    `dedupe_keys`, if given, limits the pass to those card entities.
    """
    skipped = await count_cards_unembeddable(session, dedupe_keys=dedupe_keys)
    pending = await get_cards_pending_embedding(session, dedupe_keys=dedupe_keys)
    for start in range(0, len(pending), chunk_size):
        chunk = pending[start : start + chunk_size]
        vectors = await embedding_client.embed_documents([normalized_description for _, normalized_description in chunk])
        for (dedupe_key, _), vector in zip(chunk, vectors, strict=True):
            await session.execute(
                update(CardEnrichment).where(CardEnrichment.dedupe_key == dedupe_key).values(vector=vector)
            )
        await session.commit()

    return EmbeddingPassReport(embedded=len(pending), skipped=skipped)
