from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_card as _card
from tests.factories import make_enrichment as _enrichment


async def test_card_detail_returns_the_full_printed_record(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            _card(id="swsh1-1", dedupe_key="charizard", name="Charizard", hp=170, types=["Fire"]),
            _enrichment(dedupe_key="charizard", tags=["acceleration"]),
        ]
    )
    await db_session.commit()

    response = await client.get("/cards/charizard")

    assert response.status_code == 200
    body = response.json()
    assert body["entity_id"] == "charizard"
    assert body["printing_id"] == "swsh1-1"
    assert body["name"] == "Charizard"
    assert body["hp"] == 170
    assert body["types"] == ["Fire"]
    assert body["attacks"] == []
    assert body["abilities"] == []
    assert body["attack_costs"] == [4]
    assert body["image"] == "https://assets.tcgdex.net/en/swsh/swsh1/1"
    assert body["tags"] == ["acceleration"]


async def test_card_detail_never_exposes_normalized_description(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            _card(id="swsh1-1", dedupe_key="charizard"),
            _enrichment(dedupe_key="charizard", normalized_description="attach extra energy and burn"),
        ]
    )
    await db_session.commit()

    response = await client.get("/cards/charizard")

    assert "normalized_description" not in response.json()


async def test_card_detail_lists_all_printings_of_the_entity(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            _card(id="swsh1-1", dedupe_key="charizard", set_id="swsh1", release_date=date(2020, 1, 1)),
            _card(id="swsh4-1", dedupe_key="charizard", set_id="swsh4", release_date=date(2021, 1, 1)),
        ]
    )
    await db_session.commit()

    response = await client.get("/cards/charizard")

    body = response.json()
    assert body["printing_id"] == "swsh4-1"  # representative = most recent
    assert [p["printing_id"] for p in body["printings"]] == ["swsh4-1", "swsh1-1"]


async def test_card_detail_tags_are_empty_when_enrichment_is_not_completed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.enrichment import status

    db_session.add_all(
        [
            _card(id="swsh1-1", dedupe_key="charizard"),
            _enrichment(dedupe_key="charizard", tags=["acceleration"], status=status.PENDING),
        ]
    )
    await db_session.commit()

    response = await client.get("/cards/charizard")

    assert response.json()["tags"] == []


async def test_card_detail_tags_are_empty_without_an_enrichment_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all([_card(id="swsh1-1", dedupe_key="charizard")])
    await db_session.commit()

    response = await client.get("/cards/charizard")

    assert response.status_code == 200
    assert response.json()["tags"] == []


async def test_card_detail_passes_through_the_matched_chip_from_search(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all([_card(id="swsh1-1", dedupe_key="charizard")])
    await db_session.commit()

    response = await client.get(
        "/cards/charizard", params={"matched_tags": ["acceleration"], "matched_semantic": "true"}
    )

    assert response.json()["matched"] == {"tags": ["acceleration"], "semantic": True}


async def test_card_detail_matched_is_null_when_not_reached_via_search(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all([_card(id="swsh1-1", dedupe_key="charizard")])
    await db_session.commit()

    response = await client.get("/cards/charizard")

    assert response.json()["matched"] is None


async def test_card_detail_404s_for_an_unknown_entity(client: AsyncClient, db_session: AsyncSession) -> None:
    response = await client.get("/cards/does-not-exist")

    assert response.status_code == 404
