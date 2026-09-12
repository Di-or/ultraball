import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.parse_client import ParseClient
from app.search.models import Filters
from app.search.parse import PARSE_VERSION, enforce_filters, normalize_query
from app.search.parse_cache import get_cached_parse, make_cache_key, store_parse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedGate:
    """The filter gate to run, and — on a degraded parse — the keyword to match on `name`."""

    filters: Filters
    keyword: str | None = None
    tags: list[str] = field(default_factory=list)


async def resolve_search_gate(
    session: AsyncSession, parse_client: ParseClient, query: str | None, fallback_filters: Filters
) -> ResolvedGate:
    """Fills the gate from a natural-language `query`, or passes structured filters through.

    A repeat query hits the lexical parse cache and never re-invokes the model.
    A parse failure degrades to keyword search over `name` plus the default
    Standard gate — never a 500 (CONTEXT.md: Parse object).
    """
    if not query:
        return ResolvedGate(filters=fallback_filters)

    cache_key = make_cache_key(normalize_query(query), PARSE_VERSION)
    cached = await get_cached_parse(session, cache_key)
    if cached is not None:
        return ResolvedGate(filters=enforce_filters(cached.filters), tags=list(cached.tags))

    try:
        result = await parse_client.parse(query)
    except Exception:
        logger.exception("parse: degrading to keyword search for query=%r", query)
        return ResolvedGate(filters=Filters(format="standard"), keyword=query)

    await store_parse(session, cache_key, result)
    return ResolvedGate(filters=enforce_filters(result.filters), tags=list(result.tags))
