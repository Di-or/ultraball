from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_card as _card


async def test_a_fully_resolvable_list_imports_and_returns_the_resolved_deck(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            _card(id="obf-10", dedupe_key="charmander", name="Charmander", set_id="obf", set_code="OBF", local_id="10"),
            _card(
                id="base1-98",
                dedupe_key="fire-energy",
                name="Fire Energy",
                category="Energy",
                energy_type="Basic",
                stage=None,
                set_id="base1",
                set_code="BASE1",
                local_id="98",
            ),
        ]
    )
    await db_session.commit()

    response = await client.post(
        "/decks/import",
        json={"text": "4 Charmander OBF 10\n8 Basic Fire Energy"},
    )

    assert response.status_code == 200
    body = response.json()
    assert {"printing_id": "obf-10", "count": 4} in body["entries"]
    assert {"printing_id": "base1-98", "count": 8} in body["entries"]


async def test_an_unresolvable_line_fails_the_whole_import(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [_card(id="obf-10", dedupe_key="charmander", name="Charmander", set_id="obf", set_code="OBF", local_id="10")]
    )
    await db_session.commit()

    response = await client.post(
        "/decks/import",
        json={"text": "4 Charmander OBF 10\n2 Not A Real Card XYZ 999"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "2 Not A Real Card XYZ 999" in detail["lines"]


async def test_resolves_a_basic_energy_line_via_the_most_recent_printing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            _card(
                id="base1-98",
                dedupe_key="fire-energy",
                name="Fire Energy",
                category="Energy",
                energy_type="Basic",
                stage=None,
                set_id="base1",
                set_code="BASE1",
                local_id="98",
                release_date=date(1999, 1, 9),
            ),
            _card(
                id="base4-98",
                dedupe_key="fire-energy",
                name="Fire Energy",
                category="Energy",
                energy_type="Basic",
                stage=None,
                set_id="base4",
                set_code="BASE4",
                local_id="98",
                release_date=date(2020, 1, 1),
            ),
        ]
    )
    await db_session.commit()

    response = await client.post("/decks/import", json={"text": "10 Fire Energy"})

    assert response.status_code == 200
    body = response.json()
    assert body["entries"] == [{"printing_id": "base4-98", "count": 10}]
