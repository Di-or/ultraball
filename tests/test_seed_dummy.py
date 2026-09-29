from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Card
from app.enrichment.models import CardEnrichment
from scripts.seed_dummy import SNAPSHOTS, seed


async def test_seeding_twice_leaves_the_same_data_and_sets_list_newest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed(db_session)
    first = await _counts(db_session)
    await seed(db_session)

    assert await _counts(db_session) == first
    assert first[0] == sum(len(s.cards) for s in SNAPSHOTS.values())
    assert first[1] == first[2] > 0

    response = await client.get("/sets")
    assert [s["id"] for s in response.json()] == ["dummy3", "dummy2", "dummy1"]


async def _counts(session: AsyncSession) -> tuple[int, int, int]:
    cards = await session.scalar(select(func.count()).select_from(Card))
    enrichments = await session.scalar(select(func.count()).select_from(CardEnrichment))
    vectors = await session.scalar(
        select(func.count()).select_from(CardEnrichment).where(CardEnrichment.vector.is_not(None))
    )
    return cards, enrichments, vectors
