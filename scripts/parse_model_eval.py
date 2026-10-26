"""Measure the hosted parse call across models and reasoning efforts (#85).

Run by hand: `uv run python -m scripts.parse_model_eval`. Needs OPENAI_API_KEY and
CLAUDE_API_KEY (or ANTHROPIC_API_KEY), from the env or `.env`, plus CLAUDE_WORKSPACE_ID when
the Claude key isn't scoped to a workspace. Not part of the app or CI; costs well under $1
per run.

Sends the production parse request (system prompt and schema built by
`app.clients.parse_client` from the fixed set list in `parse_eval_sets.json`, so it tracks
prompt changes) for every query in `parse_eval_queries.json`, 3 runs per configuration after
one warm-up call, with a 60s timeout instead of the client's 4s so slow configurations still
get measured. Claude models get the same prompt and schema through the Messages API, with the
system prompt marked for caching. Queries marked `"difficulty": "hard"` are scored in their
own row so they don't move the standard numbers. Raw calls go to `--raw` (default
`research/parse-model-eval-haiku-raw.json`); the report tables are printed as Markdown.
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

import anthropic
import httpx

from app.catalog.set_models import CatalogSet
from app.clients.parse_client import _OPENAI_CHAT_URL, build_parse_json_schema, build_system_prompt
from app.config import Settings

QUERIES_PATH = Path(__file__).with_name("parse_eval_queries.json")
SETS_PATH = Path(__file__).with_name("parse_eval_sets.json")
RAW_PATH = Path(__file__).parents[1] / "research" / "parse-model-eval-haiku-raw.json"

_TIMEOUT_SECONDS = 60.0
_RUNS = 3
_CUTOFFS = (2, 3, 4, 6, 8)
_MAX_RATE_LIMIT_RETRIES = 3
# Thinking counts against max_tokens; the parse object itself is ~100 tokens.
_CLAUDE_MAX_TOKENS = 8192
DIFFICULTIES = ("standard", "hard")


@dataclass(frozen=True)
class Config:
    model: str
    effort: str

    @property
    def is_claude(self) -> bool:
        return self.model.startswith("claude-")

    def __str__(self) -> str:
        return f"{self.model} / {self.effort}"


# Efforts are sent explicitly: both models default to `medium`, and the request should say what ran.
CONFIGS = [
    Config("gpt-5.6-luna", "low"),
    Config("gpt-5.6-luna", "medium"),
    Config("claude-haiku-5-5", "low"),
    Config("claude-haiku-5-5", "medium"),
]

# USD per 1M tokens: (uncached input, cached input, output). Reasoning tokens bill as output.
_PRICES = {
    "gpt-5-mini": (0.25, 0.025, 2.00),
    "gpt-5.6-luna": (0.20, 0.02, 1.20),
    "claude-haiku-5-5": (0.10, 0.01, 0.50),
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


class _EvalSettings(Settings):
    """The app's settings plus the Claude key, which only this script needs."""

    claude_api_key: str | None = None
    anthropic_api_key: str | None = None
    # Sent as `anthropic-workspace-id`; only needed for a key not scoped to a workspace.
    claude_workspace_id: str | None = None


def load_sets() -> tuple[CatalogSet, ...]:
    """The catalog's set list as of the SV-to-Mega corpus, fixed so runs are comparable."""
    return tuple(CatalogSet(**s) for s in json.loads(SETS_PATH.read_text(encoding="utf-8")))


def request_body(config: Config, query: str, sets: tuple[CatalogSet, ...]) -> dict:
    """The production parse request, plus an explicit `reasoning_effort`."""
    return {
        "model": config.model,
        "reasoning_effort": config.effort,
        "messages": [
            {"role": "system", "content": build_system_prompt(sets)},
            {"role": "user", "content": query},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "parse_object", "strict": True, "schema": build_parse_json_schema(sets)},
        },
    }


def claude_schema(schema):
    """The parse schema in the form Anthropic's structured outputs accept, allowing the same values.

    Anthropic rejects a type list like `["string", "null"]` alongside an enum that includes
    `null`; each nullable node becomes `anyOf: [<the non-null node>, {"type": "null"}]`.
    """
    if isinstance(schema, list):
        return [claude_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    node = {key: claude_schema(value) for key, value in schema.items()}
    types = node.get("type")
    if isinstance(types, list) and "null" in types:
        rest = [t for t in types if t != "null"]
        node["type"] = rest[0] if len(rest) == 1 else rest
        if "enum" in node:
            node["enum"] = [v for v in node["enum"] if v is not None]
        return {"anyOf": [node, {"type": "null"}]}
    return node


def claude_request(config: Config, query: str, sets: tuple[CatalogSet, ...]) -> dict:
    """The same prompt and schema as a Messages API request, with the system prompt cached."""
    return {
        "model": config.model,
        "max_tokens": _CLAUDE_MAX_TOKENS,
        "system": [{"type": "text", "text": build_system_prompt(sets), "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": query}],
        "output_config": {
            "effort": config.effort,
            "format": {"type": "json_schema", "schema": claude_schema(build_parse_json_schema(sets))},
        },
    }


def claude_usage(usage: dict) -> dict:
    """Anthropic's usage in the Chat Completions shape the summary reads, keeping the original.

    Anthropic's `input_tokens` excludes cache reads and writes; Chat Completions'
    `prompt_tokens` includes them.
    """
    cached, written = usage.get("cache_read_input_tokens") or 0, usage.get("cache_creation_input_tokens") or 0
    thinking = (usage.get("output_tokens_details") or {}).get("thinking_tokens")
    return {
        "prompt_tokens": usage["input_tokens"] + cached + written,
        "prompt_tokens_details": {"cached_tokens": cached, "cache_write_tokens": written},
        "completion_tokens": usage["output_tokens"],
        "completion_tokens_details": {"reasoning_tokens": thinking},
        "anthropic": usage,
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
    # gpt-5.6-luna and Claude report cache writes; they bill at 1.25× the uncached input rate.
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


def difficulty(query: dict) -> str:
    return query.get("difficulty", "standard")


def summarise(calls: list[Call], queries: list[dict]) -> Summary:
    """One configuration's measured calls (warm-ups excluded) against the query set.

    Quality (filters, tags) is scored over the calls that answered; failures go in `errors`.
    """
    by_query = {q["query"]: q for q in queries}
    answered = _answered(calls)
    if not answered:
        nan = math.nan
        return Summary(len(calls), len(calls), nan, nan, dict.fromkeys(_CUTOFFS, 0.0), nan, nan, nan, nan, nan, nan, nan)
    latencies = [answer.latency for _, answer in answered]
    usages = [answer.usage for _, answer in answered]

    true_positives = predicted = expected = 0
    for call, answer in answered:
        got, want = set(answer.output["tags"]), set(by_query[call.query]["tags"])
        true_positives += len(got & want)
        predicted += len(got)
        expected += len(want)

    reasoning = [u["completion_tokens_details"]["reasoning_tokens"] for u in usages]
    prompt_tokens = sum(u["prompt_tokens"] for u in usages)
    return Summary(
        calls=len(calls),
        errors=len(calls) - len(answered),
        median_latency=statistics.median(latencies),
        p95_latency=_percentile(latencies, 0.95),
        within={cutoff: sum(lat <= cutoff for lat in latencies) / len(calls) for cutoff in _CUTOFFS},
        mean_reasoning_tokens=math.nan if None in reasoning else statistics.mean(reasoning),
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
    for by_config in grouped.values():
        for outcomes in by_config.values():
            outcomes.sort(key=lambda outcome: json.dumps(outcome, sort_keys=True))
    return {
        query: by_config
        for query, by_config in grouped.items()
        if any(outcomes != next(iter(by_config.values())) for outcomes in by_config.values())
    }


async def _post_openai(config: Config, query: str, sets: tuple[CatalogSet, ...], api_key: str) -> tuple[dict, dict] | None:
    """(usage, parsed output), or None when rate-limited."""
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        response = await client.post(
            _OPENAI_CHAT_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=request_body(config, query, sets),
        )
    if response.status_code == 429:
        return None
    response.raise_for_status()
    payload = response.json()
    return payload["usage"], json.loads(payload["choices"][0]["message"]["content"])


async def _post_claude(
    config: Config, query: str, sets: tuple[CatalogSet, ...], auth: tuple[str, str | None]
) -> tuple[dict, dict] | None:
    """(usage, parsed output), or None when rate-limited or overloaded."""
    api_key, workspace_id = auth
    headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None
    async with anthropic.AsyncAnthropic(
        api_key=api_key, timeout=_TIMEOUT_SECONDS, max_retries=0, default_headers=headers
    ) as client:
        try:
            message = await client.messages.create(**claude_request(config, query, sets))
        except anthropic.RateLimitError:
            return None
        except anthropic.APIStatusError as exc:
            if exc.status_code == 529:
                return None
            raise
    if message.stop_reason != "end_turn":
        raise ValueError(f"stop_reason {message.stop_reason}")
    text = next(block.text for block in message.content if block.type == "text")
    return claude_usage(message.usage.to_dict()), json.loads(text)


async def _measure(
    config: Config, query: str, run: int, sets: tuple[CatalogSet, ...], auth, *, warmup: bool = False
) -> Call:
    # A fresh client per call, as HostedParseClient does, so connection setup is included.
    post = _post_claude if config.is_claude else _post_openai
    for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
        started = time.perf_counter()
        try:
            result = await post(config, query, sets, auth)
            latency = time.perf_counter() - started
            if result is None:
                if attempt < _MAX_RATE_LIMIT_RETRIES:
                    await asyncio.sleep(2**attempt * 5)
                    continue
                return Call(config, query, run, None, "rate-limited after retries", warmup)
            usage, output = result
            return Call(config, query, run, Answer(latency, usage, output), warmup=warmup)
        except (httpx.HTTPError, anthropic.APIError, KeyError, StopIteration, ValueError) as exc:
            detail = exc.response.text[:300] if isinstance(exc, httpx.HTTPStatusError) else ""
            error = f"{type(exc).__name__}: {exc} {detail}".strip()
            return Call(config, query, run, None, error, warmup)
    raise AssertionError("unreachable")


async def _measure_config(config: Config, queries: list[dict], sets: tuple[CatalogSet, ...], auth) -> list[Call]:
    warmup = await _measure(config, queries[0]["query"], 0, sets, auth, warmup=True)
    if warmup.error is not None:
        raise SystemExit(f"{config}: warm-up call failed: {warmup.error}")
    calls = [warmup]
    for run in range(1, _RUNS + 1):
        for query in queries:
            calls.append(await _measure(config, query["query"], run, sets, auth))
        print(f"{config}: run {run}/{_RUNS} done", file=sys.stderr)
    return calls


async def _run_all(queries: list[dict], sets: tuple[CatalogSet, ...], keys: dict[bool, object]) -> list[Call]:
    # Configurations run side by side; calls within one run one at a time.
    per_config = await asyncio.gather(*(_measure_config(c, queries, sets, keys[c.is_claude]) for c in CONFIGS))
    return [call for calls in per_config for call in calls]


def _save(calls: list[Call], path: Path) -> None:
    # One call per line: compact, and still readable in a diff.
    lines = ",\n".join(json.dumps(asdict(c), ensure_ascii=False) for c in calls)
    path.write_text(f"[\n{lines}\n]\n", encoding="utf-8")


def _load(path: Path) -> list[Call]:
    calls = []
    for c in json.loads(path.read_text(encoding="utf-8")):
        answer = Answer(**c["answer"]) if c["answer"] is not None else None
        calls.append(Call(**{**c, "config": Config(**c["config"]), "answer": answer}))
    return calls


def _percent(value: float) -> str:
    return f"{value:.0%}"


def _tokens(value: float) -> str:
    return "n/a" if math.isnan(value) else f"{value:.0f}"


def _render_outcome(outcome: Outcome) -> str:
    filters, tags = outcome
    rendered_filters = json.dumps(filters, ensure_ascii=False) if filters else "{}"
    return f"`{rendered_filters}` · {', '.join(tags) or '(no tags)'}"


_REWRITE_SAMPLES = (
    "energy accel",
    "stall the opponent",
    "put damage counters on their bench",
    "stadium that punishes ex",
    "punish them for attacking me",
)


def report(calls: list[Call], queries: list[dict]) -> str:
    measured = [c for c in calls if not c.warmup]
    # Configurations in the order they ran, so older raw files still render.
    configs = list(dict.fromkeys(c.config for c in calls))
    level = {q["query"]: difficulty(q) for q in queries}
    counts = {d: sum(difficulty(q) == d for q in queries) for d in DIFFICULTIES}
    lines = [
        f"Standard: {counts['standard']} queries. Hard: {counts['hard']} queries, scored separately.",
        "",
        "| Configuration | Cases | Calls | Errors | Median | p95 | ≤2s | ≤3s | ≤4s | ≤6s | ≤8s "
        "| Reasoning tok | Completion tok | Cached | Filters exact | Tag P | Tag R | $ / 1k queries |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: "
        "| ---: | ---: | ---: |",
    ]
    for config in configs:
        for cases in DIFFICULTIES:
            subset = [c for c in measured if c.config == config and level.get(c.query) == cases]
            if not subset:
                continue
            s = summarise(subset, queries)
            within = " | ".join(_percent(s.within[cutoff]) for cutoff in _CUTOFFS)
            lines.append(
                f"| `{config}` | {cases} | {s.calls} | {s.errors} | {s.median_latency:.2f}s | {s.p95_latency:.2f}s "
                f"| {within} | {_tokens(s.mean_reasoning_tokens)} | {s.mean_completion_tokens:.0f} "
                f"| {_percent(s.cached_share)} | {_percent(s.filter_match_rate)} | {s.tag_precision:.2f} "
                f"| {s.tag_recall:.2f} | ${s.cost_per_1000:.3f} |"
            )

    answers = _answered(calls)
    prompt = sum(a.usage["prompt_tokens"] for _, a in answers)
    cached = sum(a.usage["prompt_tokens_details"]["cached_tokens"] for _, a in answers)
    completion = sum(a.usage["completion_tokens"] for _, a in answers)
    reasoning = sum(a.usage["completion_tokens_details"]["reasoning_tokens"] or 0 for _, a in answers)
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
        if query not in level:
            continue
        lines += [f"**{query}**", "", "| Configuration | `concept_rewritten` |", "| --- | --- |"]
        for config in configs:
            sample = next((a for c, a in _answered(measured) if c.config == config and c.query == query), None)
            text = sample.output["concept_rewritten"] if sample else "(failed)"
            lines.append(f"| `{config}` | {text or '(empty)'} |")
        lines.append("")

    expected = {q["query"]: q for q in queries}
    lines += ["### Per-query disagreements", ""]
    for query, by_config in disagreements(measured).items():
        q = expected[query]
        want = (normalise_filters(q["filters"]), tuple(sorted(q["tags"])))
        marker = " — hard" if difficulty(q) == "hard" else ""
        lines += [
            f"**{query}**{marker} (expected {_render_outcome(want)})",
            "",
            f"| Configuration | Distinct outputs across {_RUNS} runs |",
            "| --- | --- |",
        ]
        for config in configs:
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
    parser.add_argument("--raw", type=Path, default=RAW_PATH, help="raw results file to write or read")
    args = parser.parse_args()

    queries = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    if args.report:
        calls = _load(args.raw)
    else:
        settings = _EvalSettings()
        claude_key = settings.claude_api_key or settings.anthropic_api_key
        if not settings.openai_api_key:
            raise SystemExit("OPENAI_API_KEY is not set")
        if not claude_key:
            raise SystemExit("CLAUDE_API_KEY (or ANTHROPIC_API_KEY) is not set")
        # OpenAI takes the bare key; Claude takes (key, workspace id).
        keys = {False: settings.openai_api_key, True: (claude_key, settings.claude_workspace_id)}
        calls = asyncio.run(_run_all(queries, load_sets(), keys))
        _save(calls, args.raw)
    # The tables use non-ASCII (≤, ·); Windows consoles default to a legacy code page.
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    out.write(report(calls, queries) + "\n")
    out.flush()


if __name__ == "__main__":
    main()
