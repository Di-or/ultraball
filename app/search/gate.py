import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.embedding_client import EmbeddingClient
from app.clients.parse_client import ParseClient, ParseResult
from app.search.embedding_cache import (
    EMBED_VERSION,
    get_cached_embedding,
    make_embedding_cache_key,
    store_embedding,
)
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
    query_vector: list[float] | None = None


async def _resolve_query_vector(
    session: AsyncSession, embedding_client: EmbeddingClient, concept_rewritten: str
) -> list[float] | None:
    """Embeds `concept_rewritten` (CONTEXT.md: Query/passage asymmetry), cached.

    An embedding failure degrades to skipping the semantic path — never a 500,
    mirroring the parse degrade above.
    """
    cache_key = make_embedding_cache_key(normalize_query(concept_rewritten), EMBED_VERSION)
    cached = await get_cached_embedding(session, cache_key)
    if cached is not None:
        return cached

    try:
        vector = await embedding_client.embed_query(concept_rewritten)
    except Exception:
        logger.exception("embed: skipping semantic path for concept_rewritten=%r", concept_rewritten)
        return None

    await store_embedding(session, cache_key, vector)
    return vector


async def resolve_search_gate(
    session: AsyncSession,
    parse_client: ParseClient,
    embedding_client: EmbeddingClient,
    query: str | None,
    fallback_filters: Filters,
) -> ResolvedGate:
    """Fills the gate from a natural-language `query`, or passes structured filters through.

    A repeat query hits the lexical parse cache and never re-invokes the model.
    A parse failure degrades to keyword search over `name` plus the default
    Standard gate — never a 500 (CONTEXT.md: Parse object). An empty
    `concept_rewritten` skips the semantic path entirely (CONTEXT.md: Semantic search).
    """
    if not query:
        return ResolvedGate(filters=fallback_filters)

    cache_key = make_cache_key(normalize_query(query), PARSE_VERSION)
    cached = await get_cached_parse(session, cache_key)
    parsed: ParseResult
    if cached is not None:
        parsed = cached
    else:
        try:
            parsed = await parse_client.parse(query)
        except Exception:
            logger.exception("parse: degrading to keyword search for query=%r", query)
            return ResolvedGate(filters=Filters(format="standard"), keyword=query)
        await store_parse(session, cache_key, parsed)

    query_vector = None
    if parsed.concept_rewritten:
        query_vector = await _resolve_query_vector(session, embedding_client, parsed.concept_rewritten)

    return ResolvedGate(
        filters=enforce_filters(parsed.filters),
        tags=list(parsed.tags),
        query_vector=query_vector,
    )
