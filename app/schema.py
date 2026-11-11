from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.catalog.models import Base as CatalogBase
from app.enrichment.models import Base as EnrichmentBase
from app.search.embedding_cache import Base as QueryEmbeddingCacheBase
from app.search.parse_cache import Base as ParseCacheBase


async def create_schema(engine: AsyncEngine) -> None:
    """Creates any missing table or column the app needs. Safe to run on every start."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(CatalogBase.metadata.create_all)
        # `create_all` never adds a column to an existing table; backfill `set_name` (issue #90)
        # on a database from before it. Re-running ingest (or the seed script) fills real names.
        await conn.execute(text("ALTER TABLE cards ADD COLUMN IF NOT EXISTS set_name VARCHAR NOT NULL DEFAULT ''"))
        # Likewise `is_textless` (issue #113): re-running ingest marks the textless printings.
        await conn.execute(
            text("ALTER TABLE cards ADD COLUMN IF NOT EXISTS is_textless BOOLEAN NOT NULL DEFAULT false")
        )
        await conn.run_sync(EnrichmentBase.metadata.create_all)
        await conn.run_sync(ParseCacheBase.metadata.create_all)
        await conn.run_sync(QueryEmbeddingCacheBase.metadata.create_all)
