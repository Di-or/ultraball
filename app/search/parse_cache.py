from datetime import datetime

from sqlalchemy import ARRAY, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.clients.parse_client import ParseResult


class Base(DeclarativeBase):
    pass


class ParseCacheEntry(Base):
    """Lexical memo of the parse step only, not results (CONTEXT.md: Parse cache).

    Keyed on normalize(query)+parse_version so a repeat query skips the hosted
    model entirely; a `parse_version` bump changes the key rather than requiring
    an explicit flush, so stale entries simply stop being hit.
    """

    __tablename__ = "parse_cache"

    cache_key: Mapped[str] = mapped_column(String, primary_key=True)

    filters: Mapped[dict] = mapped_column(JSONB)
    concept: Mapped[str] = mapped_column(String)
    concept_rewritten: Mapped[str] = mapped_column(String)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def make_cache_key(normalized_query: str, parse_version: str) -> str:
    return f"{normalized_query}:{parse_version}"


async def get_cached_parse(session: AsyncSession, cache_key: str) -> ParseResult | None:
    entry = await session.get(ParseCacheEntry, cache_key)
    if entry is None:
        return None
    return ParseResult(
        filters=entry.filters,
        concept=entry.concept,
        concept_rewritten=entry.concept_rewritten,
        tags=list(entry.tags),
    )


async def store_parse(session: AsyncSession, cache_key: str, result: ParseResult) -> None:
    session.add(
        ParseCacheEntry(
            cache_key=cache_key,
            filters=result.filters,
            concept=result.concept,
            concept_rewritten=result.concept_rewritten,
            tags=result.tags,
        )
    )
    await session.commit()
