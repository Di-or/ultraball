import json

import httpx
import pytest

from app.catalog.set_models import CatalogSet
from app.clients import parse_client
from app.clients.parse_client import HostedParseClient, build_parse_json_schema, build_system_prompt
from app.enrichment.taxonomy import TAG_DEFINITIONS, TAG_EXAMPLES

_PARSE_OBJECT = {
    "filters": {
        "format": None,
        "category": "Pokemon",
        "sub_category": None,
        "types": None,
        "hp": {"gte": None, "lte": 130},
        "retreat": {"gte": None, "lte": None},
        "attack_cost": {"gte": None, "lte": None},
        "stage": None,
        "trainer_type": None,
        "energy_type": None,
        "set_id": None,
    },
    "concept": "energy accel",
    "concept_rewritten": "attach extra Energy beyond the one-per-turn attachment",
    "tags": [],
}


@pytest.fixture
def sent_requests(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    """Answers the hosted parse call with a canned completion, recording what was sent."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        completion = {"choices": [{"message": {"content": json.dumps(_PARSE_OBJECT)}}]}
        return httpx.Response(200, json=completion)

    real_async_client = httpx.AsyncClient

    def mocked_async_client(**kwargs: object) -> httpx.AsyncClient:
        return real_async_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(parse_client.httpx, "AsyncClient", mocked_async_client)
    return requests


async def test_hosted_parse_request_is_strict_gpt_6_luna_at_low_effort_without_temperature(
    sent_requests: list[httpx.Request],
) -> None:
    # gpt-6-luna is a reasoning model: it only accepts the default temperature, and it
    # defaults to `medium` effort, so `low` (what the eval measured, #94) is sent explicitly.
    await HostedParseClient(api_key="test-key").parse("energy accel pokemon under 130 HP", ())

    body = json.loads(sent_requests[-1].content)
    assert "temperature" not in body
    assert body["model"] == "gpt-6-luna"
    assert body["reasoning_effort"] == "low"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True


async def test_hosted_parse_request_gives_up_after_six_seconds(sent_requests: list[httpx.Request]) -> None:
    # GPT-6 Luna at low effort finished only 90-93% of calls within 4s, 98-100% within 6s (#94).
    await HostedParseClient(api_key="test-key").parse("energy accel", ())

    assert sent_requests[-1].extensions["timeout"] == {"connect": 6.0, "read": 6.0, "write": 6.0, "pool": 6.0}


async def test_hosted_parse_system_prompt_carries_every_tag_definition(
    sent_requests: list[httpx.Request],
) -> None:
    # The parser must draw the same line between tags as the enricher, so it reads the
    # same definitions (and examples) rather than bare tag names.
    await HostedParseClient(api_key="test-key").parse("energy accel", ())

    body = json.loads(sent_requests[-1].content)
    system_prompt = body["messages"][0]["content"]
    for tag, definition in TAG_DEFINITIONS.items():
        assert f"{tag}: {definition}" in system_prompt
        for example in TAG_EXAMPLES[tag]:
            assert example.name in system_prompt


async def test_hosted_parse_system_prompt_keeps_effect_phrasing_out_of_numeric_filters(
    sent_requests: list[httpx.Request],
) -> None:
    # A `retreat` filter is a hard gate and Trainers have no retreat value, so "retreat for
    # free" filled as retreat=0 drops every Switch-type and retreat-cost Trainer (#89).
    await HostedParseClient(api_key="test-key").parse("retreat for free", ())

    system_prompt = json.loads(sent_requests[-1].content)["messages"][0]["content"]
    # Numeric filters only for a stated number or the card's printed stat.
    for stat_phrase in ('"0 retreat"', '"no retreat cost"', '"free retreat Pokémon"'):
        assert stat_phrase in system_prompt
    for effect_phrase in ('"retreat for free"', '"switch out"'):
        assert effect_phrase in system_prompt
    # No overlap: the same words never land in both filters and concept.
    assert "Never encode the same words in both `filters` and `concept`" in system_prompt


def test_system_prompt_reads_under_and_over_as_exclusive_bounds() -> None:
    # Players read "under 90 HP" as excluding 90; "N or less" / "at least N" include N (#94).
    # The examples avoid the eval queries' numbers, so the prompt isn't taught the test.
    system_prompt = build_system_prompt(())

    assert '"under 90 HP" is hp.lte=89' in system_prompt
    assert '"over 200 HP" is hp.gte=201' in system_prompt
    assert '"3 retreat or less" is retreat.lte=3' in system_prompt
    assert '"at least 2 retreat" is retreat.gte=2' in system_prompt
    assert "hp.lte=130" not in system_prompt


def test_system_prompt_carries_the_parse_rules_the_eval_trialled_after_the_tag_glossary() -> None:
    # Trialled as `--prompt rules` in the parse eval (#94). They live in the parse instructions,
    # not the tag glossary, which also drives enrichment.
    system_prompt = build_system_prompt(())
    instructions = system_prompt[system_prompt.index("You split a") :]

    # Category only for the kind of card wanted, not what the effect acts on.
    assert "Fill `category` only when the query says what kind of card it wants" in instructions
    # Bench damage with no count given gets both tags.
    assert "tag both `snipe` and `spread`" in instructions
    # A goal with no described effect gets no guessed mechanism.
    assert "Tag only effects the query describes" in instructions
    # Damage counters aren't damage.
    assert "Placing damage counters is not dealing damage" in instructions


_SETS = (
    CatalogSet(id="sv06", code="TWM", name="Twilight Masquerade"),
    CatalogSet(id="sv01", code="SVI", name="Scarlet & Violet"),
)


def test_system_prompt_lists_each_set_by_id_code_and_name_in_id_order() -> None:
    system_prompt = build_system_prompt(_SETS)

    first = system_prompt.index("sv01 — SVI — Scarlet & Violet")
    second = system_prompt.index("sv06 — TWM — Twilight Masquerade")
    assert first < second


def test_system_prompt_is_identical_for_the_same_set_list() -> None:
    # Byte-identical text keeps the hosted model's prompt cache warm, whatever order the sets arrive in.
    assert build_system_prompt(_SETS) == build_system_prompt(tuple(reversed(_SETS)))


def test_system_prompt_puts_the_set_list_ahead_of_the_instructions() -> None:
    system_prompt = build_system_prompt(_SETS)

    assert system_prompt.index("sv06 — TWM — Twilight Masquerade") < system_prompt.index("You split a")


def test_system_prompt_tells_the_model_to_resolve_a_named_set_to_its_listed_id() -> None:
    system_prompt = build_system_prompt(_SETS)

    assert "fill `set_id` with that set's id from the list" in system_prompt
    for phrase in ("name", "PTCGL code", "id"):
        assert phrase in system_prompt


def test_schema_limits_set_id_to_the_listed_ids_plus_null() -> None:
    schema = build_parse_json_schema(_SETS)

    assert schema["properties"]["filters"]["properties"]["set_id"]["enum"] == ["sv01", "sv06", None]


def test_schema_limits_energy_type_to_the_stored_values_plus_null() -> None:
    # Cards store `Basic` or `Special`; free text like "Special Energy" matched nothing (#94).
    schema = build_parse_json_schema(_SETS)

    assert schema["properties"]["filters"]["properties"]["energy_type"]["enum"] == ["Basic", "Special", None]


def test_schema_with_an_empty_catalog_allows_only_a_null_set_id() -> None:
    schema = build_parse_json_schema(())

    set_id = schema["properties"]["filters"]["properties"]["set_id"]
    assert set_id["enum"] == [None]
    assert "set_id" in schema["properties"]["filters"]["required"]


async def test_hosted_parse_request_carries_the_set_list_prompt_and_schema(
    sent_requests: list[httpx.Request],
) -> None:
    await HostedParseClient(api_key="test-key").parse("supporters from Twilight Masquerade", _SETS)

    body = json.loads(sent_requests[-1].content)
    assert body["messages"][0]["content"] == build_system_prompt(_SETS)
    assert body["response_format"]["json_schema"]["schema"] == build_parse_json_schema(_SETS)
