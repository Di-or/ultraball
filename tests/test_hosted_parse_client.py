import json

import httpx
import pytest

from app.clients import parse_client
from app.clients.parse_client import HostedParseClient
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


async def test_hosted_parse_request_is_strict_gpt_5_mini_without_temperature(
    sent_requests: list[httpx.Request],
) -> None:
    # gpt-5-mini is a reasoning model: it only accepts the default temperature.
    await HostedParseClient(api_key="test-key").parse("energy accel pokemon under 130 HP")

    body = json.loads(sent_requests[-1].content)
    assert "temperature" not in body
    assert body["model"] == "gpt-5-mini"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True


async def test_hosted_parse_system_prompt_carries_every_tag_definition(
    sent_requests: list[httpx.Request],
) -> None:
    # The parser must draw the same line between tags as the enricher, so it reads the
    # same definitions (and examples) rather than bare tag names.
    await HostedParseClient(api_key="test-key").parse("energy accel")

    body = json.loads(sent_requests[-1].content)
    system_prompt = body["messages"][0]["content"]
    for tag, definition in TAG_DEFINITIONS.items():
        assert f"{tag}: {definition}" in system_prompt
        for example in TAG_EXAMPLES[tag]:
            assert example.name in system_prompt
