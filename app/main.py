from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Base as CatalogBase
from app.config import Settings
from app.db import make_engine, make_session_factory
from app.enrichment.models import Base as EnrichmentBase
from app.search.models import SearchRequest, SearchResponse, SearchResult
from app.search.queries import run_search


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(CatalogBase.metadata.create_all)
            await conn.run_sync(EnrichmentBase.metadata.create_all)
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
        cards, total = await run_search(
            session, request.filters, request.facets, limit=request.limit, offset=request.offset
        )
        return SearchResponse(
            results=[SearchResult.from_card(card) for card in cards],
            total=total,
            limit=request.limit,
            offset=request.offset,
        )

    return app


app = create_app()
