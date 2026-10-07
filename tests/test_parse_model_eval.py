import json
import math
from pathlib import Path

import pytest

from app.clients import parse_client
from scripts.parse_model_eval import (
    CONFIGS,
    QUERIES_PATH,
    Answer,
    Call,
    Config,
    call_cost,
    disagreements,
    filters_match,
    normalise_filters,
    request_body,
    summarise,
)


def _call(
    query: str = "energy accel",
    latency: float = 1.0,
    *,
    config: Config = Config("gpt-5-mini", "minimal"),
    filters: dict | None = None,
    tags: list[str] | None = None,
    prompt: int = 1000,
    cached: int = 800,
    completion: int = 100,
    reasoning: int = 50,
    error: str | None = None,
) -> Call:
    if error is not None:
        return Call(config=config, query=query, run=1, answer=None, error=error)
    return Call(
        config=config,
        query=query,
        run=1,
        answer=Answer(
            latency=latency,
            usage=_usage(prompt, cached, completion, reasoning),
            output={"filters": filters or {}, "concept": query, "concept_rewritten": query, "tags": tags or []},
        ),
    )


def _usage(prompt: int = 1000, cached: int = 800, completion: int = 100, reasoning: int = 50) -> dict:
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "prompt_tokens_details": {"cached_tokens": cached},
        "completion_tokens_details": {"reasoning_tokens": reasoning},
    }


def test_request_body_is_the_production_prompt_and_schema_with_an_explicit_effort() -> None:
    body = request_body(Config("gpt-5.6-luna", "none"), "energy accel")

    assert body["model"] == "gpt-5.6-luna"
    assert body["reasoning_effort"] == "none"
    assert body["messages"] == [
        {"role": "system", "content": parse_client._SYSTEM_PROMPT},
        {"role": "user", "content": "energy accel"},
    ]
    assert body["response_format"]["json_schema"]["schema"] is parse_client._PARSE_JSON_SCHEMA
    assert body["response_format"]["json_schema"]["strict"] is True


def test_the_six_configurations_cover_both_models_at_three_efforts() -> None:
    assert CONFIGS == [
        Config("gpt-5-mini", "minimal"),
        Config("gpt-5-mini", "low"),
        Config("gpt-5-mini", "medium"),
        Config("gpt-5.6-luna", "none"),
        Config("gpt-5.6-luna", "low"),
        Config("gpt-5.6-luna", "medium"),
    ]


def test_normalised_filters_drop_strict_mode_nulls_and_empty_ranges() -> None:
    raw = {
        "format": None,
        "category": "Pokemon",
        "sub_category": None,
        "types": ["Water", "Fire"],
        "hp": {"gte": None, "lte": 130},
        "retreat": {"gte": None, "lte": None},
        "attack_cost": {"gte": None, "lte": None},
        "stage": None,
        "trainer_type": None,
        "energy_type": None,
        "set_id": None,
    }

    assert normalise_filters(raw) == {"category": "Pokemon", "types": ["Fire", "Water"], "hp": {"lte": 130}}


def test_filters_match_any_accepted_reading() -> None:
    query = {"filters": {"trainer_type": "Supporter"}, "filters_also": [{"category": "Trainer", "trainer_type": "Supporter"}]}

    assert filters_match({"trainer_type": "Supporter"}, query)
    assert filters_match({"category": "Trainer", "trainer_type": "Supporter"}, query)
    assert not filters_match({"trainer_type": "Item"}, query)


def test_call_cost_bills_uncached_cached_and_output_tokens_at_the_models_rates() -> None:
    usage = _usage(prompt=1000, cached=800, completion=100)

    # gpt-5-mini: 200 × $0.25 + 800 × $0.025 + 100 × $2.00, per 1M tokens.
    assert call_cost("gpt-5-mini", usage) == pytest.approx((200 * 0.25 + 800 * 0.025 + 100 * 2.00) / 1e6)
    # gpt-5.6-luna: 200 × $0.20 + 800 × $0.02 + 100 × $1.20, per 1M tokens.
    assert call_cost("gpt-5.6-luna", usage) == pytest.approx((200 * 0.20 + 800 * 0.02 + 100 * 1.20) / 1e6)


def test_call_cost_bills_cache_writes_at_a_quarter_over_the_uncached_rate() -> None:
    usage = _usage(prompt=1000, cached=0, completion=100)
    usage["prompt_tokens_details"]["cache_write_tokens"] = 900

    # gpt-5.6-luna: 100 uncached × $0.20 + 900 written × $0.25 + 100 × $1.20, per 1M tokens.
    assert call_cost("gpt-5.6-luna", usage) == pytest.approx((100 * 0.20 + 900 * 0.25 + 100 * 1.20) / 1e6)


def test_summary_reports_latency_tokens_quality_and_cost() -> None:
    queries = [
        {"query": "energy accel", "filters": {}, "tags": ["acceleration"]},
        {"query": "big hp basic", "filters": {"stage": "Basic"}, "tags": []},
    ]
    calls = [
        _call("energy accel", 1.0, tags=["acceleration"]),
        _call("energy accel", 2.5, tags=["acceleration", "search"]),
        _call("big hp basic", 5.0, filters={"stage": "Basic"}),
        _call("big hp basic", error="timeout"),
    ]

    summary = summarise(calls, queries)

    assert summary.calls == 4
    assert summary.errors == 1
    assert summary.median_latency == 2.5
    assert summary.p95_latency == 5.0
    # Failed calls count as finishing within no cut-off.
    assert summary.within == {2: 0.25, 3: 0.5, 4: 0.5, 6: 0.75, 8: 0.75}
    assert summary.mean_reasoning_tokens == 50
    assert summary.mean_completion_tokens == 100
    assert summary.cached_share == 0.8
    # Quality is scored over the calls that answered; failures are counted in `errors`.
    assert summary.filter_match_rate == 1.0
    # Predicted tags: acceleration, acceleration, search. Expected: acceleration twice.
    assert summary.tag_precision == pytest.approx(2 / 3)
    assert summary.tag_recall == 1.0
    assert summary.cost_per_1000 == pytest.approx(call_cost("gpt-5-mini", _usage()) * 1000)


def test_disagreements_list_queries_whose_outputs_differ_between_configurations() -> None:
    mini, luna = Config("gpt-5-mini", "low"), Config("gpt-5.6-luna", "low")
    calls = [
        _call("energy accel", config=mini, tags=["acceleration"]),
        _call("energy accel", config=luna, tags=["acceleration"]),
        _call("stall the opponent", config=mini, tags=["stall"]),
        _call("stall the opponent", config=luna, tags=["stall", "item-lock"]),
    ]

    assert disagreements(calls) == {
        "stall the opponent": {
            mini: [({}, ("stall",))],
            luna: [({}, ("item-lock", "stall"))],
        }
    }


def test_configurations_with_the_same_outcomes_in_a_different_order_agree() -> None:
    mini, luna = Config("gpt-5-mini", "low"), Config("gpt-5.6-luna", "low")
    calls = [
        _call("heal my pokemon", config=mini, tags=["healing"]),
        _call("heal my pokemon", config=mini, tags=["condition-heal"]),
        _call("heal my pokemon", config=luna, tags=["condition-heal"]),
        _call("heal my pokemon", config=luna, tags=["healing"]),
    ]

    assert disagreements(calls) == {}


def test_summary_of_a_configuration_whose_calls_all_failed_reports_only_errors() -> None:
    summary = summarise([_call(error="timeout"), _call(error="timeout")], [{"query": "energy accel", "tags": []}])

    assert summary.calls == summary.errors == 2
    assert summary.within == {2: 0.0, 3: 0.0, 4: 0.0, 6: 0.0, 8: 0.0}
    assert math.isnan(summary.median_latency)
    assert math.isnan(summary.tag_precision)


def test_query_set_uses_only_known_tags_and_filter_fields() -> None:
    queries = json.loads(Path(QUERIES_PATH).read_text(encoding="utf-8"))
    filter_fields = set(parse_client._FILTERS_SCHEMA["properties"])

    assert len(queries) == 25
    assert len({q["query"] for q in queries}) == 25
    for query in queries:
        assert set(query["tags"]) <= parse_client.FUNCTIONAL_TAGS, query["query"]
        for accepted in [query["filters"], *query.get("filters_also", [])]:
            assert set(accepted) <= filter_fields, query["query"]
