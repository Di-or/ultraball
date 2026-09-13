from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.deck_models import DeckValidateRequest, DeckValidateResponse
from app.catalog.deck_validation import DeckLine, validate_deck
from app.catalog.detail_models import CardDetail
from app.catalog.models import Base as CatalogBase
from app.catalog.queries import get_cards_by_ids, get_printings
from app.clients.embedding_client import EmbeddingClient, HostedEmbeddingClient
from app.clients.parse_client import HostedParseClient, ParseClient
from app.config import Settings
from app.db import make_engine, make_session_factory
from app.enrichment import status as enrichment_status
from app.enrichment.models import Base as EnrichmentBase
from app.enrichment.models import CardEnrichment
from app.search.embedding_cache import Base as QueryEmbeddingCacheBase
from app.search.gate import resolve_search_gate
from app.search.models import Matched, SearchRequest, SearchResponse, SearchResult
from app.search.parse_cache import Base as ParseCacheBase
from app.search.queries import run_rrf_search, run_search, run_semantic_search, run_tag_match_search


def create_app(
    settings: Settings | None = None,
    *,
    parse_client: ParseClient | None = None,
    embedding_client: EmbeddingClient | None = None,
) -> FastAPI:
    settings = settings or Settings()
    parse_client = parse_client or HostedParseClient(api_key=settings.openai_api_key or "")
    embedding_client = embedding_client or HostedEmbeddingClient(api_key=settings.voyage_api_key or "")
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(CatalogBase.metadata.create_all)
            await conn.run_sync(EnrichmentBase.metadata.create_all)
            await conn.run_sync(ParseCacheBase.metadata.create_all)
            await conn.run_sync(QueryEmbeddingCacheBase.metadata.create_all)
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
        gate = await resolve_search_gate(
            session, parse_client, embedding_client, request.query, request.filters
        )

        if gate.tags and gate.query_vector is not None:
            ranked, total = await run_rrf_search(
                session,
                gate.filters,
                request.facets,
                gate.tags,
                gate.query_vector,
                limit=request.limit,
                offset=request.offset,
            )
            results = [
                SearchResult.from_card(card, matched=Matched(tags=matched_tags, semantic=matched_semantic))
                for card, matched_tags, matched_semantic in ranked
            ]
        elif gate.tags:
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
        elif gate.query_vector is not None:
            cards, total = await run_semantic_search(
                session,
                gate.filters,
                request.facets,
                gate.query_vector,
                limit=request.limit,
                offset=request.offset,
            )
            results = [SearchResult.from_card(card, matched=Matched(semantic=True)) for card in cards]
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

    @app.get("/cards/{entity_id}")
    async def card_detail(
        entity_id: str,
        matched_tags: list[str] | None = Query(default=None),
        matched_semantic: bool = Query(default=False),
        session: AsyncSession = Depends(get_session),
    ) -> CardDetail:
        printings = await get_printings(session, entity_id)
        if not printings:
            raise HTTPException(status_code=404, detail="card not found")
        card = printings[0]  # newest-first (CONTEXT.md: Representative printing)

        enrichment = await session.get(CardEnrichment, entity_id)
        tags = enrichment.tags if enrichment and enrichment.status == enrichment_status.COMPLETED else []

        matched = (
            Matched(tags=matched_tags or [], semantic=matched_semantic)
            if matched_tags or matched_semantic
            else None
        )

        return CardDetail.from_card(card, tags=tags, printings=printings, matched=matched)

    @app.post("/decks/validate")
    async def validate_deck_endpoint(
        request: DeckValidateRequest, session: AsyncSession = Depends(get_session)
    ) -> DeckValidateResponse:
        cards_by_id = {
            card.id: card for card in await get_cards_by_ids(session, [e.printing_id for e in request.entries])
        }

        lines: list[DeckLine] = []
        unresolved: list[str] = []
        for entry in request.entries:
            card = cards_by_id.get(entry.printing_id)
            if card is None:
                unresolved.append(entry.printing_id)
            else:
                lines.append(DeckLine(card=card, count=entry.count))

        report = validate_deck(lines, unresolved_printing_ids=unresolved)
        return DeckValidateResponse.from_report(report)

    return app


app = create_app()
