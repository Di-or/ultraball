from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.community.postgres import PostgresContainer

from app.clients.parse_client import ParseClient, ParseResult
from app.config import Settings
from app.main import create_app
from app.search.parse_cache import ParseCacheEntry
from tests.factories import make_card as _card
from tests.factories import make_enrichment as _enrichment
from tests.stubs import StubParseClient


class _CountingParseClient(ParseClient):
    """Wraps a stub and counts how many times the hosted model would be invoked."""

    def __init__(self, canned: ParseResult) -> None:
        self._stub = StubParseClient(canned)
        self.call_count = 0

    async def parse(self, query: str) -> ParseResult:
        self.call_count += 1
        return await self._stub.parse(query)


class _FailingParseClient(ParseClient):
    async def parse(self, query: str) -> ParseResult:
        raise RuntimeError("hosted parse model unavailable")


@asynccontextmanager
async def _client_with_parse_client(
    postgres_container: PostgresContainer, parse_client: ParseClient
) -> AsyncIterator[AsyncClient]:
    settings = Settings(database_url=postgres_container.get_connection_url())
    app = create_app(settings, parse_client=parse_client)

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


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
    body = response.json()
    assert body["results"] == []
    assert body["total"] == 0


async def test_search_query_fills_the_gate_from_the_parse_object(
    postgres_container: PostgresContainer, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            _card(id="a", dedupe_key="a", name="Charizard", hp=170),
            _enrichment(dedupe_key="a", tags=["acceleration"]),
            _card(id="b", dedupe_key="b", name="Regieleki", hp=90),
            _enrichment(dedupe_key="b", tags=["acceleration"]),
        ]
    )
    await db_session.commit()

    canned = ParseResult(filters={"hp": {"lte": 130}}, concept="acceleration", tags=["acceleration"])
    async with _client_with_parse_client(postgres_container, StubParseClient(canned)) as client:
        response = await client.post("/search", json={"query": "energy accel under 130 HP"})

    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["name"] == "Regieleki"
    assert body["filters"]["hp"] == {"gte": None, "lte": 130}
    assert body["filters"]["format"] == "standard"


async def test_search_a_parse_failure_degrades_to_keyword_plus_standard(
    postgres_container: PostgresContainer, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            _card(id="a", dedupe_key="a", name="Charizard", is_standard_legal=True),
            _card(id="b", dedupe_key="b", name="Blastoise", is_standard_legal=False),
        ]
    )
    await db_session.commit()

    async with _client_with_parse_client(postgres_container, _FailingParseClient()) as client:
        response = await client.post("/search", json={"query": "charizard"})

    assert response.status_code == 200
    body = response.json()
    assert body["filters"]["format"] == "standard"
    assert [r["name"] for r in body["results"]] == ["Charizard"]


async def test_search_a_repeat_query_does_not_re_invoke_the_parse_model(
    postgres_container: PostgresContainer, db_session: AsyncSession
) -> None:
    canned = ParseResult(filters={"category": "Pokemon"})
    counting_client = _CountingParseClient(canned)

    async with _client_with_parse_client(postgres_container, counting_client) as client:
        await client.post("/search", json={"query": "  Energy   Accel  "})
        await client.post("/search", json={"query": "energy accel"})

    assert counting_client.call_count == 1
    cached = await db_session.scalars(select(ParseCacheEntry))
    assert len(list(cached)) == 1


async def test_search_query_with_tags_routes_to_tag_match_ranking(
    postgres_container: PostgresContainer, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            _card(id="a", dedupe_key="a", name="Charizard"),
            _enrichment(dedupe_key="a", tags=["draw", "search"]),
            _card(id="b", dedupe_key="b", name="Blastoise"),
            _enrichment(dedupe_key="b", tags=["draw"]),
            _card(id="c", dedupe_key="c", name="Pikachu"),
            _enrichment(dedupe_key="c", tags=["gust"]),
        ]
    )
    await db_session.commit()

    canned = ParseResult(filters={}, concept="draw power", tags=["draw", "search"])
    async with _client_with_parse_client(postgres_container, StubParseClient(canned)) as client:
        response = await client.post("/search", json={"query": "cards that draw and search"})

    body = response.json()
    assert body["total"] == 2
    assert [r["name"] for r in body["results"]] == ["Charizard", "Blastoise"]
    assert body["results"][0]["matched"]["tags"] == ["draw", "search"]
    assert body["results"][1]["matched"]["tags"] == ["draw"]


async def test_search_without_tags_carries_no_matched_signals(client: AsyncClient, db_session: AsyncSession) -> None:
    db_session.add_all([_card(id="a", dedupe_key="a", name="Charizard")])
    await db_session.commit()

    response = await client.post("/search", json={})

    body = response.json()
    assert body["results"][0]["matched"] is None
