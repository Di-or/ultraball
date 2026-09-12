import logging
from typing import Any

from pydantic import ValidationError

from app.search.models import Filters

logger = logging.getLogger(__name__)

# Bumped whenever the filters schema changes (a new enum value, a new field) —
# invalidates the lexical parse cache without an explicit flush (CONTEXT.md: Parse cache).
PARSE_VERSION = "v1"


def normalize_query(query: str) -> str:
    """Lowercase, whitespace-collapsed form used as the parse-cache key basis."""
    return " ".join(query.strip().lower().split())


def enforce_filters(raw_filters: dict[str, Any]) -> Filters:
    """Builds a `Filters` object, dropping (and logging) any field that fails validation.

    Validated one field at a time against the `Filters` model itself, so the
    model's own enums/ranges are the single source of truth and one bad value
    from the parse model never sinks the whole query (CONTEXT.md: Parse object —
    "drop the offending filter and log it, never fail the query").
    """
    valid: dict[str, Any] = {}
    for name, value in raw_filters.items():
        if name not in Filters.model_fields:
            logger.warning("parse: dropping unknown filter field %r", name)
            continue
        try:
            Filters.model_validate({name: value})
        except ValidationError:
            logger.warning("parse: dropping invalid filter %s=%r", name, value)
            continue
        valid[name] = value

    return Filters(**valid)
