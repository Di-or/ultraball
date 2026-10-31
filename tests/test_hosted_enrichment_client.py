import hashlib
import json
from typing import Any

import httpx2
import pytest
from anthropic import DefaultAsyncHttpxClient

from app.clients import enrichment_client
from app.clients.enrichment_client import EnrichmentRequest, EnrichmentResult, HostedEnrichmentClient
from app.enrichment import status
from app.enrichment.taxonomy import FUNCTIONAL_TAGS, TAG_DEFINITIONS

_NEST_BALL = EnrichmentRequest(
    dedupe_key="nest ball search your deck for a basic pokémon and put it onto your bench.",
    canonical_card_text="Nest Ball\nItem\nSearch your deck for a Basic Pokémon and put it onto your Bench.",
)
_POTION = EnrichmentRequest(
    dedupe_key="potion heal 30 damage from 1 of your pokémon.",
    canonical_card_text="Potion\nItem\nHeal 30 damage from 1 of your Pokémon.",
)


def _custom_id(dedupe_key: str) -> str:
    return hashlib.sha256(dedupe_key.encode()).hexdigest()


def _succeeded(dedupe_key: str, output: dict, *, stop_reason: str = "end_turn") -> dict:
    return {
        "custom_id": _custom_id(dedupe_key),
        "result": {
            "type": "succeeded",
            "message": {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-5-5",
                "content": [{"type": "thinking", "thinking": "", "signature": "sig"}, {"type": "text", "text": json.dumps(output)}],
                "stop_reason": stop_reason,
                "usage": {"input_tokens": 10, "output_tokens": 10},
            },
        },
    }


class _FakeBatchesApi:
    """Answers the three Message Batches endpoints, recording each created batch's body."""

    def __init__(self, *, processing_status: str = "ended", results: list[dict] | None = None) -> None:
        self.processing_status = processing_status
        self.results = results or []
        self.created_bodies: list[dict] = []
        self.workspace_ids: list[str | None] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.workspace_ids.append(request.headers.get("anthropic-workspace-id"))
        path = request.url.path
        if request.method == "POST" and path == "/v1/messages/batches":
            self.created_bodies.append(json.loads(request.content))
            return httpx2.Response(200, json=self._batch("msgbatch_1", "in_progress"))
        if path.endswith("/results"):
            jsonl = "\n".join(json.dumps(result) for result in self.results)
            return httpx2.Response(200, content=jsonl.encode())
        batch_id = path.rsplit("/", 1)[-1]
        return httpx2.Response(200, json=self._batch(batch_id, self.processing_status))

    @staticmethod
    def _batch(batch_id: str, processing_status: str) -> dict:
        return {
            "id": batch_id,
            "type": "message_batch",
            "processing_status": processing_status,
            "results_url": f"https://api.anthropic.com/v1/messages/batches/{batch_id}/results"
            if processing_status == "ended"
            else None,
        }


@pytest.fixture
def batches_api(monkeypatch: pytest.MonkeyPatch) -> _FakeBatchesApi:
    api = _FakeBatchesApi()
    real_async_anthropic = enrichment_client.AsyncAnthropic

    def mocked_async_anthropic(**kwargs: Any) -> Any:
        http_client = DefaultAsyncHttpxClient(transport=httpx2.MockTransport(api.handle))
        return real_async_anthropic(http_client=http_client, max_retries=0, **kwargs)

    monkeypatch.setattr(enrichment_client, "AsyncAnthropic", mocked_async_anthropic)
    return api


async def test_submit_sends_one_sonnet_5_5_request_per_card_keyed_by_a_hash_of_its_dedupe_key(
    batches_api: _FakeBatchesApi,
) -> None:
    # Anthropic limits `custom_id` to 64 chars of [a-zA-Z0-9_-], and a dedupe_key is
    # normalized card text, so its SHA-256 hex digest (exactly 64 chars) stands in for it.
    batch_id = await HostedEnrichmentClient(api_key="test-key").submit_batch([_NEST_BALL, _POTION])

    assert batch_id == "msgbatch_1"
    [body] = batches_api.created_bodies
    assert [request["custom_id"] for request in body["requests"]] == [
        _custom_id(_NEST_BALL.dedupe_key),
        _custom_id(_POTION.dedupe_key),
    ]
    for request in body["requests"]:
        assert request["params"]["model"] == "claude-sonnet-5-5"
    assert body["requests"][0]["params"]["messages"] == [{"role": "user", "content": _NEST_BALL.canonical_card_text}]


async def test_submit_leaves_out_parameters_sonnet_5_5_rejects_and_sets_effort_explicitly(
    batches_api: _FakeBatchesApi,
) -> None:
    # Sonnet 5.5 returns a 400 for a non-default temperature, disabled thinking, or a
    # forced tool_choice. Thinking stays adaptive; depth is set through effort.
    await HostedEnrichmentClient(api_key="test-key").submit_batch([_NEST_BALL])

    params = batches_api.created_bodies[0]["requests"][0]["params"]
    assert "temperature" not in params
    assert "tool_choice" not in params
    assert params["thinking"] == {"type": "adaptive"}
    assert params["output_config"]["effort"] == "high"


async def test_submit_constrains_output_to_the_enrichment_schema_with_tags_from_the_taxonomy(
    batches_api: _FakeBatchesApi,
) -> None:
    await HostedEnrichmentClient(api_key="test-key").submit_batch([_NEST_BALL])

    output_format = batches_api.created_bodies[0]["requests"][0]["params"]["output_config"]["format"]
    assert output_format["type"] == "json_schema"
    schema = output_format["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"normalized_description", "tags", "suggested_new_tag", "rationale"}
    assert schema["properties"]["tags"]["items"]["enum"] == sorted(FUNCTIONAL_TAGS)


async def test_submit_puts_the_tag_glossary_in_a_cached_system_prefix_shared_by_every_request(
    batches_api: _FakeBatchesApi,
) -> None:
    await HostedEnrichmentClient(api_key="test-key").submit_batch([_NEST_BALL, _POTION])

    [first, second] = [request["params"] for request in batches_api.created_bodies[0]["requests"]]
    assert first["system"] == second["system"]
    [system_block] = first["system"]
    assert "cache_control" in system_block
    for tag, definition in TAG_DEFINITIONS.items():
        assert f"{tag}: {definition}" in system_block["text"]
    assert _NEST_BALL.canonical_card_text not in system_block["text"]


async def test_every_call_carries_the_workspace_id_when_one_is_set(batches_api: _FakeBatchesApi) -> None:
    # A key that isn't scoped to one workspace must name the workspace on each call.
    client = HostedEnrichmentClient(api_key="test-key", workspace_id="wrkspc_1")

    await client.submit_batch([_NEST_BALL])
    await client.poll_batch("msgbatch_1")
    await client.fetch_results("msgbatch_1", [_NEST_BALL.dedupe_key])

    assert batches_api.workspace_ids and set(batches_api.workspace_ids) == {"wrkspc_1"}


@pytest.mark.parametrize(
    ("processing_status", "expected"),
    [("in_progress", status.PENDING), ("canceling", status.PENDING), ("ended", status.COMPLETED)],
)
async def test_poll_maps_processing_status_to_the_pipeline_statuses(
    batches_api: _FakeBatchesApi, processing_status: str, expected: str
) -> None:
    batches_api.processing_status = processing_status

    assert await HostedEnrichmentClient(api_key="test-key").poll_batch("msgbatch_1") == expected


async def test_fetch_maps_succeeded_results_back_to_their_dedupe_keys_in_any_order(
    batches_api: _FakeBatchesApi,
) -> None:
    potion_output = {
        "normalized_description": "Heal 30 damage from one of your Pokémon.",
        "tags": ["healing"],
        "suggested_new_tag": None,
        "rationale": "Removes damage counters.",
    }
    nest_ball_output = {
        "normalized_description": "Search your deck for a Basic Pokémon and put it onto your Bench.",
        "tags": ["search"],
        "suggested_new_tag": None,
        "rationale": "Fetches a Basic to the Bench.",
    }
    batches_api.results = [_succeeded(_POTION.dedupe_key, potion_output), _succeeded(_NEST_BALL.dedupe_key, nest_ball_output)]

    results = await HostedEnrichmentClient(api_key="test-key").fetch_results(
        "msgbatch_1", [_NEST_BALL.dedupe_key, _POTION.dedupe_key]
    )

    assert sorted(results, key=lambda result: result.dedupe_key) == [
        EnrichmentResult(dedupe_key=_NEST_BALL.dedupe_key, **nest_ball_output),
        EnrichmentResult(dedupe_key=_POTION.dedupe_key, **potion_output),
    ]


@pytest.mark.parametrize("result_type", ["errored", "expired", "canceled"])
async def test_fetch_leaves_out_requests_that_never_got_an_answer_so_they_are_retried(
    batches_api: _FakeBatchesApi, result_type: str
) -> None:
    result: dict = {"type": result_type}
    if result_type == "errored":
        result["error"] = {"type": "error", "error": {"type": "api_error", "message": "overloaded"}}
    batches_api.results = [{"custom_id": _custom_id(_NEST_BALL.dedupe_key), "result": result}]

    results = await HostedEnrichmentClient(api_key="test-key").fetch_results("msgbatch_1", [_NEST_BALL.dedupe_key])

    assert results == []


async def test_fetch_turns_an_answer_missing_a_field_into_an_empty_result_rather_than_crashing(
    batches_api: _FakeBatchesApi,
) -> None:
    batches_api.results = [_succeeded(_NEST_BALL.dedupe_key, {"tags": ["search"]})]

    results = await HostedEnrichmentClient(api_key="test-key").fetch_results("msgbatch_1", [_NEST_BALL.dedupe_key])

    assert results == [EnrichmentResult(dedupe_key=_NEST_BALL.dedupe_key)]


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
async def test_fetch_turns_a_refused_or_truncated_answer_into_an_empty_result_for_the_repair_path(
    batches_api: _FakeBatchesApi, stop_reason: str
) -> None:
    # An empty result is what the refusal-first validator routes to needs_repair.
    batches_api.results = [_succeeded(_NEST_BALL.dedupe_key, {}, stop_reason=stop_reason)]
    batches_api.results[0]["result"]["message"]["content"] = [{"type": "text", "text": '{"normalized_desc'}]

    results = await HostedEnrichmentClient(api_key="test-key").fetch_results("msgbatch_1", [_NEST_BALL.dedupe_key])

    assert results == [EnrichmentResult(dedupe_key=_NEST_BALL.dedupe_key)]
