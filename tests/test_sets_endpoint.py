from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_card as _card


async def test_returns_each_distinct_set_newest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            _card(id="swsh1-1", dedupe_key="a", set_id="swsh1", set_code="SSH", set_name="Sword & Shield", release_date=date(2020, 2, 7)),
            _card(id="swsh1-2", dedupe_key="b", set_id="swsh1", set_code="SSH", set_name="Sword & Shield", release_date=date(2020, 2, 7)),
            _card(id="sv1-1", dedupe_key="c", set_id="sv1", set_code="SVI", set_name="Scarlet & Violet", release_date=date(2023, 3, 31)),
            _card(id="base1-1", dedupe_key="d", set_id="base1", set_code="BS", set_name="Base Set", release_date=date(1999, 1, 9)),
        ]
    )
    await db_session.commit()

    response = await client.get("/sets")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "sv1", "code": "SVI", "name": "Scarlet & Violet", "release_date": "2023-03-31"},
        {"id": "swsh1", "code": "SSH", "name": "Sword & Shield", "release_date": "2020-02-07"},
        {"id": "base1", "code": "BS", "name": "Base Set", "release_date": "1999-01-09"},
    ]


async def test_a_set_with_a_backfilled_blank_name_on_some_rows_is_listed_once(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Rows from before `set_name` existed are backfilled with '' until the set is re-ingested.
    db_session.add_all(
        [
            _card(id="sv06-1", dedupe_key="a", set_id="sv06", set_code="TWM", set_name="Twilight Masquerade"),
            _card(id="sv06-2", dedupe_key="b", set_id="sv06", set_code="TWM", set_name=""),
        ]
    )
    await db_session.commit()

    response = await client.get("/sets")

    assert [(s["id"], s["name"]) for s in response.json()] == [("sv06", "Twilight Masquerade")]
