from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.embedding_client import EmbeddingClient
from app.enrichment.models import CardEnrichment
from app.enrichment.queries import get_cards_pending_embedding


async def run_embedding_pass(session: AsyncSession, embedding_client: EmbeddingClient) -> int:
    """Embed every dedupe_key that has a normalized_description but no vector yet.

    A decoupled step after tagging (#21): safe to call on its own and to
    repeat, since already-embedded rows drop out of `get_cards_pending_embedding`
    and a partial run resumes by just calling this again.

    Returns the number of dedupe_keys embedded.
    """
    pending = await get_cards_pending_embedding(session)
    if not pending:
        return 0

    dedupe_keys = [dedupe_key for dedupe_key, _ in pending]
    texts = [normalized_description for _, normalized_description in pending]
    vectors = await embedding_client.embed_documents(texts)

    for dedupe_key, vector in zip(dedupe_keys, vectors, strict=True):
        await session.execute(update(CardEnrichment).where(CardEnrichment.dedupe_key == dedupe_key).values(vector=vector))

    await session.commit()
    return len(dedupe_keys)
