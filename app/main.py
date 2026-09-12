from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Base as CatalogBase
from app.clients.parse_client import HostedParseClient, ParseClient
from app.config import Settings
from app.db import make_engine, make_session_factory
from app.enrichment.models import Base as EnrichmentBase
from app.search.gate import resolve_search_gate
from app.search.models import Matched, SearchRequest, SearchResponse, SearchResult
from app.search.parse_cache import Base as ParseCacheBase
from app.search.queries import run_search, run_tag_match_search


def create_app(settings: Settings | None = None, *, parse_client: ParseClient | None = None) -> FastAPI:
    settings = settings or Settings()
    parse_client = parse_client or HostedParseClient(api_key=settings.openai_api_key or "")
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(CatalogBase.metadata.create_all)
            await conn.run_sync(EnrichmentBase.metadata.create_all)
            await conn.run_sync(ParseCacheBase.metadata.create_all)
        yield
        await engine.dispose()

    app = FastAPI(title="Ultraball", lifespan=lifespan)
    app.state.session_factory = session_factory

    async def get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    @app.get("/health")
    async def health(session: AsyncSession = Depends(get_session)) -> dict:
        await session.execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.post("/search")
    async def search(
        request: SearchRequest, session: AsyncSession = Depends(get_session)
    ) -> SearchResponse:
        gate = await resolve_search_gate(session, parse_client, request.query, request.filters)

        if gate.tags:
            ranked, total = await run_tag_match_search(
                session,
                gate.filters,
                request.facets,
                gate.tags,
                limit=request.limit,
                offset=request.offset,
            )
            results = [
                SearchResult.from_card(card, matched=Matched(tags=matched_tags))
                for card, matched_tags in ranked
            ]
        else:
            cards, total = await run_search(
                session,
                gate.filters,
                request.facets,
                limit=request.limit,
                offset=request.offset,
                keyword=gate.keyword,
            )
            results = [SearchResult.from_card(card) for card in cards]

        return SearchResponse(
            results=results,
            total=total,
            limit=request.limit,
            offset=request.offset,
            filters=gate.filters,
        )

    return app


app = create_app()
