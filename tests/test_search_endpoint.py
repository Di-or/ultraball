from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Card


def _card(**overrides: object) -> Card:
    base = dict(
        id=overrides.pop("id", "swsh1-1"),
        set_id="swsh1",
        local_id="1",
        name="Charizard",
        category="Pokemon",
        hp=170,
        types=["Fire"],
        stage="Stage 2",
        evolve_from="Charmeleon",
        retreat=3,
        regulation_mark="H",
        rarity="Rare Holo",
        trainer_type=None,
        energy_type=None,
        attacks=[],
        abilities=[],
        attack_costs=[4],
        sub_category=[],
        dedupe_key=overrides.pop("dedupe_key", "charizard-1"),
        canonical_card_text="Charizard",
        is_standard_legal=True,
        release_date=date(2023, 1, 1),
    )
    base.update(overrides)
    return Card(**base)


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
