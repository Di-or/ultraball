from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_card as _card


async def test_search_returns_the_gated_output_contract(client: AsyncClient, db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            _card(id="a", dedupe_key="a", name="Charizard"),
            _card(id="b", dedupe_key="b", name="Blastoise", types=["Water"]),
        ]
    )
    await db_session.commit()

    response = await client.post("/search", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 30
    assert body["offset"] == 0
    assert {r["name"] for r in body["results"]} == {"Charizard", "Blastoise"}
    assert body["results"][0]["entity_id"] == "b"  # name A→Z: Blastoise before Charizard


async def test_search_applies_structured_filters(client: AsyncClient, db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            _card(id="a", dedupe_key="a", name="Charizard", types=["Fire"]),
            _card(id="b", dedupe_key="b", name="Blastoise", types=["Water"]),
        ]
    )
    await db_session.commit()

    response = await client.post("/search", json={"filters": {"types": ["Water"]}})

    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["name"] == "Blastoise"


async def test_search_empty_gate_is_not_an_error(client: AsyncClient, db_session: AsyncSession) -> None:
    response = await client.post("/search", json={"filters": {"category": "Energy"}})

    assert response.status_code == 200
    assert response.json() == {"results": [], "total": 0, "limit": 30, "offset": 0}
