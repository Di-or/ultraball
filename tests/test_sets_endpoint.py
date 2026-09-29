from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_card as _card


async def test_returns_one_entry_per_distinct_set_newest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            _card(id="swsh1-1", set_id="swsh1", set_code="SSH", release_date=date(2020, 2, 7)),
            _card(id="swsh1-2", dedupe_key="dragonite-1", set_id="swsh1", set_code="SSH", release_date=date(2020, 2, 7)),
            _card(id="sv1-1", dedupe_key="sprigatito-1", set_id="sv1", set_code="SVI", release_date=date(2023, 3, 31)),
            _card(id="base1-1", dedupe_key="alakazam-1", set_id="base1", set_code="BS", release_date=date(1999, 1, 9)),
        ]
    )
    await db_session.commit()

    response = await client.get("/sets")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "sv1", "code": "SVI", "release_date": "2023-03-31"},
        {"id": "swsh1", "code": "SSH", "release_date": "2020-02-07"},
        {"id": "base1", "code": "BS", "release_date": "1999-01-09"},
    ]


async def test_returns_empty_list_when_catalog_is_empty(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.get("/sets")

    assert response.status_code == 200
    assert response.json() == []
