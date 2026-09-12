from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.clients.embedding_client import EMBEDDING_DIM

# Bumped whenever the query embedding model/version changes — invalidates the
# cache without an explicit flush (mirrors PARSE_VERSION in app.search.parse).
EMBED_VERSION = "voyage-4-v1"


class Base(DeclarativeBase):
    pass


class QueryEmbeddingCacheEntry(Base):
    """Memo of the query-side embedding call (CONTEXT.md: Query/passage asymmetry).

    Keyed on normalize(concept_rewritten)+embed_model_version so a repeat
    concept skips the hosted embedding model entirely; an `embed_model_version`
    bump changes the key rather than requiring an explicit flush.
    """

    __tablename__ = "query_embedding_cache"

    cache_key: Mapped[str] = mapped_column(String, primary_key=True)
    vector: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def make_embedding_cache_key(normalized_concept: str, embed_model_version: str) -> str:
    return f"{normalized_concept}:{embed_model_version}"


async def get_cached_embedding(session: AsyncSession, cache_key: str) -> list[float] | None:
    entry = await session.get(QueryEmbeddingCacheEntry, cache_key)
    if entry is None:
        return None
    return list(entry.vector)


async def store_embedding(session: AsyncSession, cache_key: str, vector: list[float]) -> None:
    session.add(QueryEmbeddingCacheEntry(cache_key=cache_key, vector=vector))
    await session.commit()
