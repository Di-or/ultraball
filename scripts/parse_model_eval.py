"""Measure the hosted parse call across models and reasoning efforts (#85).

Run by hand: `uv run python -m scripts.parse_model_eval`. Needs OPENAI_API_KEY (env or
`.env`). Not part of the app or CI; costs roughly $0.25–0.75 per run.

Sends the production parse request (system prompt and schema imported from
`app.clients.parse_client`, so it tracks prompt changes) for every query in
`parse_eval_queries.json`, 3 runs per configuration after one warm-up call, with a 60s
timeout instead of the client's 4s so slow configurations still get measured. Raw calls
go to `research/parse-model-eval-raw.json`; the report tables are printed as Markdown.
`--report` re-renders the tables from the raw file without calling the API.
"""

import argparse
import asyncio
import io
import json
import math
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from app.clients.parse_client import _OPENAI_CHAT_URL, _PARSE_JSON_SCHEMA, _SYSTEM_PROMPT
from app.config import Settings

QUERIES_PATH = Path(__file__).with_name("parse_eval_queries.json")
RAW_PATH = Path(__file__).parents[1] / "research" / "parse-model-eval-raw.json"

_TIMEOUT_SECONDS = 60.0
_RUNS = 3
_CUTOFFS = (2, 3, 4, 6, 8)
_MAX_RATE_LIMIT_RETRIES = 3


@dataclass(frozen=True)
class Config:
    model: str
    effort: str

    def __str__(self) -> str:
        return f"{self.model} / {self.effort}"


# `medium` is each model's default; it is sent explicitly so the request says what ran.
CONFIGS = [
    Config("gpt-5-mini", "minimal"),
    Config("gpt-5-mini", "low"),
    Config("gpt-5-mini", "medium"),
    Config("gpt-5.6-luna", "none"),
    Config("gpt-5.6-luna", "low"),
    Config("gpt-5.6-luna", "medium"),
]

# USD per 1M tokens: (uncached input, cached input, output). Reasoning tokens bill as output.
_PRICES = {
    "gpt-5-mini": (0.25, 0.025, 2.00),
    "gpt-5.6-luna": (0.20, 0.02, 1.20),
}
_CACHE_WRITE_MULTIPLIER = 1.25

Outcome = tuple[dict, tuple[str, ...]]


@dataclass
class Answer:
    latency: float
    usage: dict
    output: dict


@dataclass
class Call:
    """One parse request; `answer` is None exactly when it failed (`error` says why)."""

    config: Config
    query: str
    run: int
    answer: Answer | None
    error: str | None = None
    warmup: bool = False


@dataclass
class Summary:
    calls: int
    errors: int
    median_latency: float
    p95_latency: float
    within: dict[int, float]
    mean_reasoning_tokens: float
    mean_completion_tokens: float
    cached_share: float
    filter_match_rate: float
    tag_precision: float
    tag_recall: float
    cost_per_1000: float


def request_body(config: Config, query: str) -> dict:
    """The production parse request, plus an explicit `reasoning_effort`."""
    return {
        "model": config.model,
        "reasoning_effort": config.effort,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "parse_object", "strict": True, "schema": _PARSE_JSON_SCHEMA},
        },
    }


def normalise_filters(filters: dict) -> dict:
    """Strict mode's nulls and empty ranges become "absent"; lists compare as sets."""
    normalised = {}
    for key, value in filters.items():
        if isinstance(value, dict):
            value = {k: v for k, v in value.items() if v is not None}
        if isinstance(value, list):
            value = sorted(value)
        if value is None or value == {} or value == []:
            continue
        normalised[key] = value
    return normalised


def filters_match(filters: dict, query: dict) -> bool:
    accepted = [query["filters"], *query.get("filters_also", [])]
    return normalise_filters(filters) in [normalise_filters(f) for f in accepted]


def call_cost(model: str, usage: dict) -> float:
    uncached_price, cached_price, output_price = _PRICES[model]
    details = usage["prompt_tokens_details"]
    cached = details["cached_tokens"]
    # Only gpt-5.6-luna reports cache writes; they bill at 1.25× the uncached input rate.
    written = details.get("cache_write_tokens", 0)
    uncached = usage["prompt_tokens"] - cached - written
    input_cost = uncached * uncached_price + written * uncached_price * _CACHE_WRITE_MULTIPLIER + cached * cached_price
    return (input_cost + usage["completion_tokens"] * output_price) / 1e6


def _percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile."""
    ordered = sorted(values)
    return ordered[max(math.ceil(fraction * len(ordered)) - 1, 0)]


def _answered(calls: list[Call]) -> list[tuple[Call, Answer]]:
    return [(call, call.answer) for call in calls if call.answer is not None]


def summarise(calls: list[Call], queries: list[dict]) -> Summary:
    """One configuration's measured calls (warm-ups excluded) against the query set.

    Quality (filters, tags) is scored over the calls that answered; failures go in `errors`.
    """
    by_query = {q["query"]: q for q in queries}
    answered = _answered(calls)
    latencies = [answer.latency for _, answer in answered]
    usages = [answer.usage for _, answer in answered]

    true_positives = predicted = expected = 0
    for call, answer in answered:
        got, want = set(answer.output["tags"]), set(by_query[call.query]["tags"])
        true_positives += len(got & want)
        predicted += len(got)
        expected += len(want)

    prompt_tokens = sum(u["prompt_tokens"] for u in usages)
    return Summary(
        calls=len(calls),
        errors=len(calls) - len(answered),
        median_latency=statistics.median(latencies),
        p95_latency=_percentile(latencies, 0.95),
        within={cutoff: sum(lat <= cutoff for lat in latencies) / len(calls) for cutoff in _CUTOFFS},
        mean_reasoning_tokens=statistics.mean(
            u["completion_tokens_details"]["reasoning_tokens"] for u in usages
        ),
        mean_completion_tokens=statistics.mean(u["completion_tokens"] for u in usages),
        cached_share=sum(u["prompt_tokens_details"]["cached_tokens"] for u in usages) / prompt_tokens,
        filter_match_rate=sum(filters_match(a.output["filters"], by_query[c.query]) for c, a in answered)
        / len(answered),
        tag_precision=true_positives / predicted if predicted else 1.0,
        tag_recall=true_positives / expected if expected else 1.0,
        cost_per_1000=statistics.mean(call_cost(c.config.model, a.usage) for c, a in answered) * 1000,
    )


def _outcome(answer: Answer) -> Outcome:
    return normalise_filters(answer.output["filters"]), tuple(sorted(answer.output["tags"]))


def disagreements(calls: list[Call]) -> dict[str, dict[Config, list[Outcome]]]:
    """Per query, each configuration's distinct (filters, tags) outcomes across its runs,
    kept only where the configurations don't all give the same outcomes."""
    grouped: dict[str, dict[Config, list[Outcome]]] = {}
    for call, answer in _answered(calls):
        outcomes = grouped.setdefault(call.query, {}).setdefault(call.config, [])
        if _outcome(answer) not in outcomes:
            outcomes.append(_outcome(answer))
    return {
        query: by_config
        for query, by_config in grouped.items()
        if any(outcomes != next(iter(by_config.values())) for outcomes in by_config.values())
    }


async def _measure(config: Config, query: str, run: int, api_key: str, *, warmup: bool = False) -> Call:
    # A fresh client per call, as HostedParseClient does, so connection setup is included.
    for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    _OPENAI_CHAT_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=request_body(config, query),
                )
            latency = time.perf_counter() - started
            if response.status_code == 429 and attempt < _MAX_RATE_LIMIT_RETRIES:
                await asyncio.sleep(2**attempt * 5)
                continue
            response.raise_for_status()
            payload = response.json()
            output = json.loads(payload["choices"][0]["message"]["content"])
            return Call(config, query, run, Answer(latency, payload["usage"], output), warmup=warmup)
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
            detail = exc.response.text[:300] if isinstance(exc, httpx.HTTPStatusError) else ""
            error = f"{type(exc).__name__}: {exc} {detail}".strip()
            return Call(config, query, run, None, error, warmup)
    raise AssertionError("unreachable")


async def _measure_config(config: Config, queries: list[dict], api_key: str) -> list[Call]:
    warmup = await _measure(config, queries[0]["query"], 0, api_key, warmup=True)
    if warmup.error is not None:
        raise SystemExit(f"{config}: warm-up call failed: {warmup.error}")
    calls = [warmup]
    for run in range(1, _RUNS + 1):
        for query in queries:
            calls.append(await _measure(config, query["query"], run, api_key))
        print(f"{config}: run {run}/{_RUNS} done", file=sys.stderr)
    return calls


async def _run_all(queries: list[dict], api_key: str) -> list[Call]:
    # Configurations run side by side; calls within one run one at a time.
    per_config = await asyncio.gather(*(_measure_config(c, queries, api_key) for c in CONFIGS))
    return [call for calls in per_config for call in calls]


def _save(calls: list[Call]) -> None:
    # One call per line: compact, and still readable in a diff.
    lines = ",\n".join(json.dumps(asdict(c), ensure_ascii=False) for c in calls)
    RAW_PATH.write_text(f"[\n{lines}\n]\n", encoding="utf-8")


def _load() -> list[Call]:
    calls = []
    for c in json.loads(RAW_PATH.read_text(encoding="utf-8")):
        answer = Answer(**c["answer"]) if c["answer"] is not None else None
        calls.append(Call(**{**c, "config": Config(**c["config"]), "answer": answer}))
    return calls


def _percent(value: float) -> str:
    return f"{value:.0%}"


def _render_outcome(outcome: Outcome) -> str:
    filters, tags = outcome
    rendered_filters = json.dumps(filters, ensure_ascii=False) if filters else "{}"
    return f"`{rendered_filters}` · {', '.join(tags) or '(no tags)'}"


_REWRITE_SAMPLES = (
    "energy accel",
    "stall the opponent",
    "put damage counters on their bench",
    "stadium that punishes ex",
    "big hp basic",
)


def report(calls: list[Call], queries: list[dict]) -> str:
    measured = [c for c in calls if not c.warmup]
    lines = [
        "| Configuration | Calls | Errors | Median | p95 | ≤2s | ≤3s | ≤4s | ≤6s | ≤8s "
        "| Reasoning tok | Completion tok | Cached | Filters exact | Tag P | Tag R | $ / 1k queries |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: "
        "| ---: | ---: | ---: |",
    ]
    for config in CONFIGS:
        s = summarise([c for c in measured if c.config == config], queries)
        within = " | ".join(_percent(s.within[cutoff]) for cutoff in _CUTOFFS)
        lines.append(
            f"| `{config}` | {s.calls} | {s.errors} | {s.median_latency:.2f}s | {s.p95_latency:.2f}s | {within} "
            f"| {s.mean_reasoning_tokens:.0f} | {s.mean_completion_tokens:.0f} | {_percent(s.cached_share)} "
            f"| {_percent(s.filter_match_rate)} | {s.tag_precision:.2f} | {s.tag_recall:.2f} "
            f"| ${s.cost_per_1000:.3f} |"
        )

    answers = [(c, a) for c, a in _answered(calls)]
    prompt = sum(a.usage["prompt_tokens"] for _, a in answers)
    cached = sum(a.usage["prompt_tokens_details"]["cached_tokens"] for _, a in answers)
    completion = sum(a.usage["completion_tokens"] for _, a in answers)
    reasoning = sum(a.usage["completion_tokens_details"]["reasoning_tokens"] for _, a in answers)
    total_cost = sum(call_cost(c.config.model, a.usage) for c, a in answers)
    lines += [
        "",
        f"Whole run ({len(calls)} calls including warm-ups, {len(calls) - len(answers)} failed): "
        f"{prompt:,} input tokens ({cached:,} cached), {completion:,} output tokens "
        f"({reasoning:,} of them reasoning), **${total_cost:.2f}**.",
        "",
        "### `concept_rewritten` samples (run 1)",
        "",
    ]
    for query in _REWRITE_SAMPLES:
        lines += [f"**{query}**", "", "| Configuration | `concept_rewritten` |", "| --- | --- |"]
        for config in CONFIGS:
            sample = next((a for c, a in _answered(measured) if c.config == config and c.query == query), None)
            text = sample.output["concept_rewritten"] if sample else "(failed)"
            lines.append(f"| `{config}` | {text or '(empty)'} |")
        lines.append("")

    expected = {q["query"]: q for q in queries}
    lines += ["### Per-query disagreements", ""]
    for query, by_config in disagreements(measured).items():
        q = expected[query]
        want = (normalise_filters(q["filters"]), tuple(sorted(q["tags"])))
        lines += [
            f"**{query}** (expected {_render_outcome(want)})",
            "",
            "| Configuration | Distinct outputs across 3 runs |",
            "| --- | --- |",
        ]
        for config in CONFIGS:
            outcomes = by_config.get(config, [])
            rendered = "<br>".join(_render_outcome(o) for o in outcomes) or "(all failed)"
            lines.append(f"| `{config}` | {rendered} |")
        lines.append("")

    errors = [c for c in calls if c.error is not None]
    if errors:
        lines += ["### Failed calls", ""]
        lines += [f"- `{c.config}` run {c.run}, “{c.query}”: {c.error}" for c in errors]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure the hosted parse call (#85).")
    parser.add_argument("--report", action="store_true", help="re-render from the saved raw results")
    args = parser.parse_args()

    queries = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    if args.report:
        calls = _load()
    else:
        api_key = Settings().openai_api_key
        if not api_key:
            raise SystemExit("OPENAI_API_KEY is not set")
        calls = asyncio.run(_run_all(queries, api_key))
        _save(calls)
    # The tables use non-ASCII (≤, ·); Windows consoles default to a legacy code page.
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    out.write(report(calls, queries) + "\n")
    out.flush()


if __name__ == "__main__":
    main()
