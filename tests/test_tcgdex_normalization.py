"""The catalog layer normalizes TCGdex's stage, regulation-mark and "None" quirks (issue #110).

TCGdex writes stages `Stage1` / `Stage2`, some regulation marks lowercase (`mep-051` is `"j"`),
and some marks and rarities as the literal string `"None"`. These tests ingest real TCGdex JSON
and drive the search endpoint, so the rest of the app is checked to see the glossary's shapes.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.community.postgres import PostgresContainer

from app.catalog.ingest import run_ingest
from app.clients.catalog_client import SetSnapshot
from app.clients.parse_client import ParseClient, ParseResult
from app.config import Settings
from app.main import create_app
from tests.factories import make_tcgdex_pokemon
from tests.stubs import StubCatalogClient, StubParseClient
from tests.tcgdex_fixtures import fixture_snapshot

# A Stage 1 written TCGdex's way. No committed fixture is a Stage 1, so this one is real-shaped.
_IVYSAUR = make_tcgdex_pokemon(id="me01-002", name="Ivysaur", stage="Stage1", evolveFrom="Bulbasaur")
_BULBASAUR = make_tcgdex_pokemon(id="me01-001")


async def _ingest(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient(
        {
            "me02": fixture_snapshot("me02", ["me02-013"]),  # Mega Charizard X ex, `"Stage2"`
            "mep": fixture_snapshot("mep", ["mep-051"]),  # Oshawott, regulation mark `"j"`
            "mfb": fixture_snapshot("mfb", ["mfb-33"]),  # Potion, mark and rarity `"None"`
            "me01": SetSnapshot("me01", date(2025, 9, 26), [_BULBASAUR, _IVYSAUR]),
        }
    )
    for set_id in ("me02", "mep", "mfb", "me01"):
        await run_ingest(db_session, catalog_client, set_id)


async def _search(client: AsyncClient, filters: dict, facets: dict | None = None) -> list[dict]:
    response = await client.post("/search", json={"filters": filters, "facets": facets or {}})
    assert response.status_code == 200
    return response.json()["results"]


@asynccontextmanager
async def _client_with_parse(
    postgres_container: PostgresContainer, parse_client: ParseClient
) -> AsyncIterator[AsyncClient]:
    app = create_app(Settings(database_url=postgres_container.get_connection_url()), parse_client=parse_client)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


async def test_the_stage_1_filter_returns_real_stage_1_cards(client: AsyncClient, db_session: AsyncSession) -> None:
    await _ingest(db_session)

    results = await _search(client, {"format": None, "stage": "Stage 1"})

    assert [(r["name"], r["stage"]) for r in results] == [("Ivysaur", "Stage 1")]


async def test_the_stage_2_filter_returns_real_stage_2_cards(client: AsyncClient, db_session: AsyncSession) -> None:
    await _ingest(db_session)

    results = await _search(client, {"format": None, "stage": "Stage 2"})

    assert [(r["name"], r["stage"]) for r in results] == [("Mega Charizard X ex", "Stage 2")]


async def test_a_parsed_stage_query_returns_real_stage_2_cards(
    postgres_container: PostgresContainer, db_session: AsyncSession
) -> None:
    await _ingest(db_session)
    canned = ParseResult(filters={"stage": "Stage 2"})

    async with _client_with_parse(postgres_container, StubParseClient(canned)) as client:
        response = await client.post("/search", json={"query": "stage 2 attackers"})

    assert [r["name"] for r in response.json()["results"]] == ["Mega Charizard X ex"]


async def test_a_lowercase_regulation_mark_is_stored_uppercase_and_standard_legal(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    results = await _search(client, {"format": "standard"}, {"regulation_mark": ["J"]})

    assert [(r["printing_id"], r["regulation_mark"]) for r in results] == [("mep-051", "J")]


async def test_a_none_regulation_mark_and_rarity_are_stored_as_missing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    results = await _search(client, {"format": None, "category": "Trainer"})

    assert [(r["name"], r["regulation_mark"], r["rarity"]) for r in results] == [("Potion", None, None)]


async def test_no_none_rarity_facet_matches_anything(client: AsyncClient, db_session: AsyncSession) -> None:
    await _ingest(db_session)

    results = await _search(client, {"format": None}, {"rarity": ["None"]})

    assert results == []
