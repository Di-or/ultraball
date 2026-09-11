from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.embedding_client import EMBEDDING_DIM
from app.enrichment import status
from app.enrichment.embedding import run_embedding_pass
from app.enrichment.models import CardEnrichment
from app.enrichment.queries import get_cards_pending_embedding
from tests.stubs import StubEmbeddingClient

_DEDUPE_KEY = "charizard|fire-spin"


async def _seed_completed_row(
    session: AsyncSession, dedupe_key: str = _DEDUPE_KEY, *, normalized_description: str | None = "Discard energy and draw a card."
) -> None:
    session.add(
        CardEnrichment(
            dedupe_key=dedupe_key,
            normalized_description=normalized_description,
            tags=["draw"],
            taxonomy_version="v1",
            prompt_version="v1",
            status=status.COMPLETED if normalized_description else status.NEEDS_REPAIR,
            batch_id="batch-1",
        )
    )
    await session.commit()


async def test_a_row_with_a_description_and_no_vector_is_pending_embedding(db_session: AsyncSession) -> None:
    await _seed_completed_row(db_session)

    pending = await get_cards_pending_embedding(db_session)

    assert pending == [(_DEDUPE_KEY, "Discard energy and draw a card.")]


async def test_a_row_without_a_description_is_never_pending(db_session: AsyncSession) -> None:
    await _seed_completed_row(db_session, normalized_description=None)

    pending = await get_cards_pending_embedding(db_session)

    assert pending == []


async def test_run_embedding_pass_embeds_pending_rows(db_session: AsyncSession) -> None:
    await _seed_completed_row(db_session)
    embedding_client = StubEmbeddingClient()

    embedded_count = await run_embedding_pass(db_session, embedding_client)

    assert embedded_count == 1
    row = await db_session.scalar(select(CardEnrichment).where(CardEnrichment.dedupe_key == _DEDUPE_KEY))
    assert row is not None
    assert row.vector is not None
    assert len(row.vector) == EMBEDDING_DIM


async def test_run_embedding_pass_on_an_unchanged_corpus_is_a_no_op(db_session: AsyncSession) -> None:
    await _seed_completed_row(db_session)
    embedding_client = StubEmbeddingClient()
    await run_embedding_pass(db_session, embedding_client)

    embedded_count = await run_embedding_pass(db_session, embedding_client)

    assert embedded_count == 0


async def test_an_embedded_row_stops_being_pending(db_session: AsyncSession) -> None:
    await _seed_completed_row(db_session)
    embedding_client = StubEmbeddingClient()
    await run_embedding_pass(db_session, embedding_client)

    pending = await get_cards_pending_embedding(db_session)

    assert pending == []
