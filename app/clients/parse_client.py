import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx

from app.enrichment.taxonomy import FUNCTIONAL_TAGS

_OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
_PARSE_MODEL = "gpt-5-mini"
# Spec's ~3-4s degrade cutoff (target <1s) (CONTEXT.md / mvp-spec §9.5): a slow
# hosted call must fail fast enough for the caller to still degrade gracefully.
_TIMEOUT_SECONDS = 4.0

_RANGE_SCHEMA = {
    "type": "object",
    "properties": {
        "gte": {"type": ["integer", "null"]},
        "lte": {"type": ["integer", "null"]},
    },
    "required": ["gte", "lte"],
    "additionalProperties": False,
}

_FILTERS_SCHEMA = {
    "type": "object",
    "properties": {
        "format": {"type": ["string", "null"], "enum": ["standard", None]},
        "category": {"type": ["string", "null"], "enum": ["Pokemon", "Trainer", "Energy", None]},
        "sub_category": {
            "type": ["array", "null"],
            "items": {"type": "string", "enum": ["ex", "mega", "ace-spec"]},
        },
        "types": {"type": ["array", "null"], "items": {"type": "string"}},
        "hp": _RANGE_SCHEMA,
        "retreat": _RANGE_SCHEMA,
        "attack_cost": _RANGE_SCHEMA,
        "stage": {"type": ["string", "null"], "enum": ["Basic", "Stage 1", "Stage 2", None]},
        "trainer_type": {
            "type": ["string", "null"],
            "enum": ["Item", "Supporter", "Stadium", "Tool", None],
        },
        "energy_type": {"type": ["string", "null"]},
        "set_id": {"type": ["string", "null"]},
    },
    "required": [
        "format",
        "category",
        "sub_category",
        "types",
        "hp",
        "retreat",
        "attack_cost",
        "stage",
        "trainer_type",
        "energy_type",
        "set_id",
    ],
    "additionalProperties": False,
}

_PARSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "filters": _FILTERS_SCHEMA,
        "concept": {"type": "string"},
        "concept_rewritten": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string", "enum": sorted(FUNCTIONAL_TAGS)}},
    },
    "required": ["filters", "concept", "concept_rewritten", "tags"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = """You split a Pokémon TCG search query into a hard filter zone and a soft \
concept, and return exactly one JSON object matching the given schema.

`filters` is closed and positive-only: fill only fields the query states explicitly (leave the \
rest null), never infer or negate. Numeric fields (hp, retreat, attack_cost) are inclusive \
{gte, lte} ranges — "under 130 HP" is hp.lte=130, "at least 2 retreat" is retreat.gte=2. \
attack_cost matches if ANY of the card's attacks falls in range. If the query does not name a \
format, leave format null (the caller defaults it to Standard).

`concept` is the residual natural-language intent not captured by filters, verbatim in spirit \
(empty string if the query is filters-only). `concept_rewritten` restates that concept in \
mechanical, card-text register (e.g. "energy accel" -> "attach extra Energy from your hand or \
deck beyond the one-per-turn attachment"), for embedding — never invent an effect the query \
didn't ask for. `tags` lists any of the fixed functional-tag enum the concept clearly matches \
(empty array if none clearly match)."""


@dataclass(frozen=True)
class ParseResult:
    """The parse object: a query split into a hard filter zone and a soft concept."""

    filters: dict = field(default_factory=dict)
    concept: str = ""
    concept_rewritten: str = ""
    tags: list[str] = field(default_factory=list)


class ParseClient(ABC):
    """Seam between the request path and the hosted parse/rewrite model."""

    @abstractmethod
    async def parse(self, query: str) -> ParseResult: ...


class HostedParseClient(ParseClient):
    """Calls the hosted parse/rewrite model (GPT-5-mini, strict JSON, temp 0)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def parse(self, query: str) -> ParseResult:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                _OPENAI_CHAT_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": _PARSE_MODEL,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": query},
                    ],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "parse_object",
                            "strict": True,
                            "schema": _PARSE_JSON_SCHEMA,
                        },
                    },
                },
            )
            response.raise_for_status()

        payload = response.json()
        parsed = json.loads(payload["choices"][0]["message"]["content"])

        filters = {name: value for name, value in parsed["filters"].items() if value is not None}
        for range_field in ("hp", "retreat", "attack_cost"):
            if range_field in filters:
                filters[range_field] = {k: v for k, v in filters[range_field].items() if v is not None}

        return ParseResult(
            filters=filters,
            concept=parsed["concept"],
            concept_rewritten=parsed["concept_rewritten"],
            tags=parsed["tags"],
        )
