import json
import math
from pathlib import Path

import pytest

from app.clients import parse_client
from scripts.parse_model_eval import (
    CONFIGS,
    PROMPT_VARIANTS,
    QUERIES_PATH,
    Answer,
    Call,
    Config,
    call_cost,
    claude_request,
    claude_schema,
    claude_usage,
    disagreements,
    filters_match,
    load_sets,
    normalise_filters,
    report,
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
    sets = load_sets()
    body = request_body(Config("gpt-5.6-luna", "low"), "energy accel", sets)

    assert body["model"] == "gpt-5.6-luna"
    assert body["reasoning_effort"] == "low"
    assert body["messages"] == [
        {"role": "system", "content": parse_client.build_system_prompt(sets)},
        {"role": "user", "content": "energy accel"},
    ]
    assert body["response_format"]["json_schema"]["schema"] == parse_client.build_parse_json_schema(sets)
    assert body["response_format"]["json_schema"]["strict"] is True


def test_claude_request_sends_the_same_prompt_and_schema_with_a_cached_system_prompt() -> None:
    sets = load_sets()
    body = claude_request(Config("claude-haiku-5-5", "low"), "energy accel", sets)

    assert body["model"] == "claude-haiku-5-5"
    assert body["system"] == [
        {"type": "text", "text": parse_client.build_system_prompt(sets), "cache_control": {"type": "ephemeral"}}
    ]
    assert body["messages"] == [{"role": "user", "content": "energy accel"}]
    assert body["output_config"] == {
        "effort": "low",
        "format": {"type": "json_schema", "schema": claude_schema(parse_client.build_parse_json_schema(sets))},
    }


def test_claude_schema_turns_nullable_type_lists_into_any_of() -> None:
    schema = {
        "type": "object",
        "properties": {
            "category": {"type": ["string", "null"], "enum": ["Pokemon", "Trainer", None]},
            "types": {"type": ["array", "null"], "items": {"type": "string"}},
            "concept": {"type": "string"},
        },
    }

    assert claude_schema(schema) == {
        "type": "object",
        "properties": {
            "category": {"anyOf": [{"type": "string", "enum": ["Pokemon", "Trainer"]}, {"type": "null"}]},
            "types": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]},
            "concept": {"type": "string"},
        },
    }


def test_claude_usage_counts_cache_reads_and_writes_as_prompt_tokens() -> None:
    usage = claude_usage(
        {
            "input_tokens": 20,
            "cache_read_input_tokens": 1500,
            "cache_creation_input_tokens": 0,
            "output_tokens": 300,
            "output_tokens_details": {"thinking_tokens": 200},
        }
    )

    assert usage["prompt_tokens"] == 1520
    assert usage["prompt_tokens_details"] == {"cached_tokens": 1500, "cache_write_tokens": 0}
    assert usage["completion_tokens"] == 300
    assert usage["completion_tokens_details"] == {"reasoning_tokens": 200}
    # Haiku 5.5: 20 × $0.10 + 1500 × $0.01 + 300 × $0.50, per 1M tokens.
    assert call_cost("claude-haiku-5-5", usage) == pytest.approx((20 * 0.10 + 1500 * 0.01 + 300 * 0.50) / 1e6)


def test_a_prompt_variant_appends_its_rules_after_the_production_prompt() -> None:
    sets = load_sets()
    production = parse_client.build_system_prompt(sets)

    luna = request_body(Config("gpt-5.6-luna", "low", "rules"), "energy accel", sets)
    haiku = claude_request(Config("claude-haiku-5-5", "low", "rules"), "energy accel", sets)

    assert luna["messages"][0]["content"] == production + "\n\n" + PROMPT_VARIANTS["rules"]
    assert haiku["system"][0]["text"] == luna["messages"][0]["content"]
    assert str(Config("claude-haiku-5-5", "low", "rules")) == "claude-haiku-5-5 / low + rules"


def test_the_configurations_cover_luna_and_haiku_at_low_and_medium() -> None:
    assert CONFIGS == [
        Config("gpt-5.6-luna", "low"),
        Config("gpt-5.6-luna", "medium"),
        Config("claude-haiku-5-5", "low"),
        Config("claude-haiku-5-5", "medium"),
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


def test_query_set_uses_only_known_tags_filter_fields_and_set_ids() -> None:
    queries = json.loads(Path(QUERIES_PATH).read_text(encoding="utf-8"))
    filter_fields = set(parse_client._FILTERS_SCHEMA["properties"]) | {"set_id"}
    set_ids = {s.id for s in load_sets()}

    assert len({q["query"] for q in queries}) == len(queries)
    assert sum(q.get("difficulty") == "hard" for q in queries) >= 15
    for query in queries:
        assert query.get("difficulty", "standard") in ("standard", "hard"), query["query"]
        assert set(query["tags"]) <= parse_client.FUNCTIONAL_TAGS, query["query"]
        for accepted in [query["filters"], *query.get("filters_also", [])]:
            assert set(accepted) <= filter_fields, query["query"]
            assert accepted.get("set_id", "sv01") in set_ids, query["query"]


def test_report_scores_hard_queries_in_their_own_row() -> None:
    luna = Config("gpt-5.6-luna", "low")
    queries = [
        {"query": "energy accel", "filters": {}, "tags": ["acceleration"]},
        {"query": "lock items and abilities", "filters": {}, "tags": ["ability-lock", "item-lock"], "difficulty": "hard"},
    ]
    calls = [
        _call("energy accel", config=luna, tags=["acceleration"]),
        _call("lock items and abilities", config=luna, tags=["item-lock"]),
    ]

    cells = [line.split(" | ") for line in report(calls, queries).splitlines()]

    standard, hard = (row for row in cells if row[0] == "| `gpt-5.6-luna / low`" and row[1] in ("standard", "hard"))
    assert standard[1] == "standard" and standard[-3:-1] == ["1.00", "1.00"]
    assert hard[1] == "hard" and hard[-3:-1] == ["1.00", "0.50"]
