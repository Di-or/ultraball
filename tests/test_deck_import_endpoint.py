from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Card
from tests.factories import make_card as _card


def _mee_fire_energy() -> Card:
    return _card(
        id="mee-002",
        dedupe_key="fire-energy",
        name="Fire Energy",
        category="Energy",
        energy_type="Basic",
        types=["Fire"],
        stage=None,
        set_id="mee",
        set_code="MEE",
        local_id="002",
    )


async def test_a_fully_resolvable_list_imports_and_returns_the_resolved_deck(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            _card(id="obf-10", dedupe_key="charmander", name="Charmander", set_id="obf", set_code="OBF", local_id="10"),
            _mee_fire_energy(),
        ]
    )
    await db_session.commit()

    response = await client.post(
        "/decks/import",
        json={"text": "4 Charmander OBF 10\n8 Basic Fire Energy"},
    )

    assert response.status_code == 200
    body = response.json()
    printing_ids = {entry["printing_id"]: entry for entry in body["entries"]}
    assert printing_ids["obf-10"]["count"] == 4
    assert printing_ids["obf-10"]["name"] == "Charmander"
    assert printing_ids["obf-10"]["category"] == "Pokemon"
    assert printing_ids["obf-10"]["set_code"] == "OBF"
    assert printing_ids["obf-10"]["local_id"] == "10"
    assert printing_ids["mee-002"]["count"] == 8
    assert printing_ids["mee-002"]["category"] == "Energy"
    assert printing_ids["mee-002"]["energy_type"] == "Basic"


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


async def test_resolves_a_bare_type_name_without_the_energy_suffix(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add(_mee_fire_energy())
    await db_session.commit()

    response = await client.post("/decks/import", json={"text": "4 Fire"})

    assert response.status_code == 200
    entries = response.json()["entries"]
    assert [(entry["printing_id"], entry["count"]) for entry in entries] == [("mee-002", 4)]


async def test_a_basic_energy_line_naming_another_basic_energy_printing_resolves_to_mee(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            _mee_fire_energy(),
            _card(
                id="base4-98",
                dedupe_key="fire-energy",
                name="Fire Energy",
                category="Energy",
                energy_type="Basic",
                types=["Fire"],
                stage=None,
                set_id="base4",
                set_code="BASE4",
                local_id="98",
            ),
        ]
    )
    await db_session.commit()

    response = await client.post("/decks/import", json={"text": "10 Fire Energy BASE4 98"})

    assert response.status_code == 200
    body = response.json()
    assert [(entry["printing_id"], entry["count"]) for entry in body["entries"]] == [("mee-002", 10)]
