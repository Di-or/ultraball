from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.ingest import run_ingest
from app.clients.catalog_client import SetSnapshot
from tests.factories import make_card as _card
from tests.factories import make_raw_pokemon
from tests.stubs import StubCatalogClient


async def test_a_legal_60_card_deck_reports_legal(client: AsyncClient, db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            _card(id="p1", dedupe_key="p1", name="Pikachu", category="Pokemon", stage="Basic"),
            _card(
                id="e1",
                dedupe_key="e1",
                name="Fire Energy",
                category="Energy",
                energy_type="Basic",
                stage=None,
            ),
        ]
    )
    await db_session.commit()

    response = await client.post(
        "/decks/validate",
        json={"entries": [{"printing_id": "p1", "count": 4}, {"printing_id": "e1", "count": 56}]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["legal"] is True
    assert body["violations"] == []
    assert body["counts"] == {"pokemon": 4, "trainer": 0, "energy": 56, "total": 60}


async def test_an_undersized_deck_is_flagged_but_not_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all([_card(id="p1", dedupe_key="p1", name="Pikachu", category="Pokemon", stage="Basic")])
    await db_session.commit()

    response = await client.post("/decks/validate", json={"entries": [{"printing_id": "p1", "count": 4}]})

    assert response.status_code == 200
    body = response.json()
    assert body["legal"] is False
    codes = [v["code"] for v in body["violations"]]
    assert "deck_size" in codes
    assert "no_basic_pokemon" not in codes  # the one Pikachu satisfies this rule


async def test_a_5th_copy_is_allowed_and_flagged_not_blocked(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            _card(id="p1", dedupe_key="p1", name="Riolu", category="Pokemon", stage="Basic"),
            _card(
                id="e1",
                dedupe_key="e1",
                name="Fire Energy",
                category="Energy",
                energy_type="Basic",
                stage=None,
            ),
        ]
    )
    await db_session.commit()

    response = await client.post(
        "/decks/validate",
        json={"entries": [{"printing_id": "p1", "count": 5}, {"printing_id": "e1", "count": 55}]},
    )

    body = response.json()
    assert response.status_code == 200
    violation = next(v for v in body["violations"] if v["code"] == "four_copy_limit")
    assert violation["cards"] == ["p1"]


async def test_an_unknown_printing_id_is_flagged_and_its_count_still_counted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/decks/validate", json={"entries": [{"printing_id": "does-not-exist", "count": 60}]}
    )

    assert response.status_code == 200
    body = response.json()
    violation = next(v for v in body["violations"] if v["code"] == "unknown_printing")
    assert violation["cards"] == ["does-not-exist"]
    assert body["counts"]["total"] == 60
    assert "deck_size" not in [v["code"] for v in body["violations"]]


async def test_an_ingested_g_card_is_flagged_not_standard_legal_under_the_current_rotation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    catalog_client = StubCatalogClient(
        {
            "me2": SetSnapshot(
                "me2", date(2025, 11, 14), [make_raw_pokemon(id="me2-1", name="Bulbasaur", regulationMark="J")]
            ),
            "sv1": SetSnapshot(
                "sv1", date(2023, 3, 31), [make_raw_pokemon(id="sv1-1", name="Sprigatito", regulationMark="G")]
            ),
        }
    )
    await run_ingest(db_session, catalog_client, "me2")
    await run_ingest(db_session, catalog_client, "sv1")

    response = await client.post(
        "/decks/validate",
        json={"entries": [{"printing_id": "me2-1", "count": 4}, {"printing_id": "sv1-1", "count": 4}]},
    )

    assert response.status_code == 200
    violation = next(v for v in response.json()["violations"] if v["code"] == "not_standard_legal")
    assert violation["cards"] == ["sv1-1"]
