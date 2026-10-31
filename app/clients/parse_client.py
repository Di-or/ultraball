import json
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field

import httpx

from app.catalog.set_models import CatalogSet, render_set_lines
from app.enrichment.taxonomy import FUNCTIONAL_TAGS, render_tag_glossary

_OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
_PARSE_MODEL = "gpt-6-luna"
# Sent explicitly: gpt-6-luna defaults to `medium`. `low` was the most accurate configuration the
# parse eval measured (#94); `none` was faster but got hard queries wrong on every run.
_PARSE_REASONING_EFFORT = "low"
# A slow hosted call must fail fast enough for the caller to still degrade gracefully
# (CONTEXT.md / mvp-spec §9.5). Raised from the spec's ~3-4s cutoff to 6s because GPT-6 Luna
# at low effort finishes only 90-93% of calls within 4s, but 98-100% within 6s (#94).
_TIMEOUT_SECONDS = 6.0

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
        "energy_type": {"type": ["string", "null"], "enum": ["Basic", "Special", None]},
        # `set_id` is added per set list by `build_parse_json_schema`.
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


def build_parse_json_schema(sets: Sequence[CatalogSet]) -> dict:
    """The strict response schema, with `set_id` limited to the listed set ids (or null)."""
    set_ids = sorted(s.id for s in sets)
    filters = {
        **_FILTERS_SCHEMA,
        "properties": {
            **_FILTERS_SCHEMA["properties"],
            "set_id": {"type": ["string", "null"], "enum": [*set_ids, None]},
        },
    }
    return {
        "type": "object",
        "properties": {
            "filters": filters,
            "concept": {"type": "string"},
            "concept_rewritten": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string", "enum": sorted(FUNCTIONAL_TAGS)}},
        },
        "required": ["filters", "concept", "concept_rewritten", "tags"],
        "additionalProperties": False,
    }


_TAG_GLOSSARY = (
    "Functional tags (what a card does). The enrichment pass tags cards with these same "
    "definitions, so pick a tag only when the query asks for that effect as defined here:\n"
    + render_tag_glossary()
)

_INSTRUCTIONS = """You split a Pokémon TCG search query into a hard filter zone and a soft \
concept, and return exactly one JSON object matching the given schema.

`filters` is closed and positive-only: fill only fields the query states explicitly (leave the \
rest null), never infer or negate. Numeric fields (hp, retreat, attack_cost) are inclusive \
{gte, lte} ranges. "Under" and "over" exclude the number: "under 90 HP" is hp.lte=89, "over \
200 HP" is hp.gte=201. "Or less", "or more", "at most" and "at least" include it: "3 retreat or \
less" is retreat.lte=3, "at least 2 retreat" is retreat.gte=2. The same holds for retreat and \
attack_cost. attack_cost matches if ANY of the card's attacks falls in range. Fill a numeric field only when \
the query states a number or describes the card's printed stat ("0 retreat", "no retreat cost", \
"free retreat Pokémon"); phrasing about doing something ("retreat for free", "switch out") is an \
effect, so it goes to `concept` and `tags`, never to a numeric filter. If the query does not name \
a format, leave format null (the caller defaults it to Standard).

If the query names a set — by its name, its PTCGL code or its id — fill `set_id` with that \
set's id from the list above (e.g. "Twilight Masquerade", "TWM" and "sv06" all mean \
set_id="sv06"). Never fill `set_id` with a value that isn't a listed id.

Never encode the same words in both `filters` and `concept`: each part of the query lands in \
exactly one of the two.

`concept` is the residual natural-language intent not captured by filters, verbatim in spirit \
(empty string if the query is filters-only). `concept_rewritten` restates that concept in \
mechanical, card-text register (e.g. "energy accel" -> "attach extra Energy from your hand or \
deck beyond the one-per-turn attachment"), for embedding — never invent an effect the query \
didn't ask for. `tags` lists any of the functional tags above that the concept clearly matches \
(empty array if none clearly match).

Further rules:
- Fill `category` only when the query says what kind of card it wants ("grass pokemon with an \
ability", "tools that boost damage"). A Pokémon or Energy the effect acts on ("shuffle my \
pokemon back into the deck", "power up my pokemon", "the opponent's pokemon", "move energy \
between my pokemon") is not the card's category, so leave `category` null.
- If the query asks for damage to the opponent's Bench without saying whether one Pokémon or \
several are hit, tag both `snipe` and `spread`.
- Tag only effects the query describes. If it names a goal without describing any effect \
("good against big attackers", "tool that beats Charizard"), don't guess a mechanism the card \
might use: leave `tags` empty and let `concept` carry it. A query that does describe the effect \
still gets its tag ("hurt them back when they hit me" describes damage back when hit, \
`counter-damage`; "nothing can damage it next turn" describes damage being prevented, \
`damage-prevention`).
- Placing damage counters is not dealing damage: don't add `snipe` or `spread` to a query about \
damage counters, or `counter-placement` to a query about dealing damage."""


def build_system_prompt(sets: Sequence[CatalogSet]) -> str:
    """The parse system prompt: tag glossary, then the catalog's set list, then the instructions.

    The glossary and set list lead because they only change on a taxonomy bump or a
    restart after ingest, so they stay inside the hosted model's cached prompt prefix.
    """
    set_list = (
        "Sets in the catalog, one per line as `id — PTCGL code — name`. `set_id` takes the id:\n"
        + (render_set_lines(sets) or "(none)")
    )
    return _TAG_GLOSSARY + "\n\n" + set_list + "\n\n" + _INSTRUCTIONS


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
    async def parse(self, query: str, sets: Sequence[CatalogSet]) -> ParseResult:
        """Parses `query`, resolving a named set against `sets` (the catalog's set list)."""


def _drop_nulls(obj: dict) -> dict:
    """Strips strict-JSON-mode's required-but-unset `null`s back to "absent"."""
    return {key: value for key, value in obj.items() if value is not None}


class HostedParseClient(ParseClient):
    """Calls the hosted parse/rewrite model (GPT-6 Luna at low effort, strict JSON)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def parse(self, query: str, sets: Sequence[CatalogSet]) -> ParseResult:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                _OPENAI_CHAT_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": _PARSE_MODEL,
                    "reasoning_effort": _PARSE_REASONING_EFFORT,
                    "messages": [
                        {"role": "system", "content": build_system_prompt(sets)},
                        {"role": "user", "content": query},
                    ],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "parse_object",
                            "strict": True,
                            "schema": build_parse_json_schema(sets),
                        },
                    },
                },
            )
            response.raise_for_status()

        payload = response.json()
        parsed = json.loads(payload["choices"][0]["message"]["content"])

        filters = _drop_nulls(parsed["filters"])
        for range_field in ("hp", "retreat", "attack_cost"):
            if range_field in filters:
                filters[range_field] = _drop_nulls(filters[range_field])

        return ParseResult(
            filters=filters,
            concept=parsed["concept"],
            concept_rewritten=parsed["concept_rewritten"],
            tags=parsed["tags"],
        )
