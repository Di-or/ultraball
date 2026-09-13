from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_card as _card


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


async def test_an_unknown_printing_id_is_flagged_rather_than_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/decks/validate", json={"entries": [{"printing_id": "does-not-exist", "count": 60}]}
    )

    assert response.status_code == 200
    body = response.json()
    violation = next(v for v in body["violations"] if v["code"] == "unknown_printing")
    assert violation["cards"] == ["does-not-exist"]
