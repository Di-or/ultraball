import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlockParam
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from app.enrichment import status
from app.enrichment.taxonomy import FUNCTIONAL_TAGS, render_tag_glossary


@dataclass(frozen=True)
class EnrichmentRequest:
    """One dedupe_key's canonical_card_text queued for a Batch enrichment call."""

    dedupe_key: str
    canonical_card_text: str


@dataclass(frozen=True)
class EnrichmentResult:
    """One dedupe_key's tagged, described output from a Batch enrichment call."""

    dedupe_key: str
    normalized_description: str = ""
    tags: list[str] = field(default_factory=list)
    suggested_new_tag: str | None = None
    rationale: str = ""


class EnrichmentClient(ABC):
    """Seam between the enrichment pipeline and the hosted Batch model.

    Submit/poll/fetch instead of one blocking call because Batch runs are
    long-lived and must be resumable: a mid-run crash resumes by polling the
    stored `batch_id` rather than resubmitting the whole corpus
    (CONTEXT.md: Enrichment identity).
    """

    @abstractmethod
    async def submit_batch(self, requests: list[EnrichmentRequest]) -> str: ...

    @abstractmethod
    async def poll_batch(self, batch_id: str) -> str: ...

    @abstractmethod
    async def fetch_results(self, batch_id: str, dedupe_keys: list[str]) -> list[EnrichmentResult]:
        """Results for the batch's `dedupe_keys` (the caller's record of what it submitted).

        A key with no answer (the request errored, expired or was canceled) is left out,
        so the caller can put it back up for the next submit.
        """


_ENRICHMENT_MODEL = "claude-sonnet-5-5"
# Sent explicitly so a change to the model's default can't silently change tag quality.
# `high` is Sonnet 5.5's default; `medium` is still to be compared on the gold set.
_ENRICHMENT_EFFORT = "high"
# Thinking counts toward max_tokens; the JSON answer itself is a few hundred tokens.
_MAX_TOKENS = 16000

ENRICHMENT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "normalized_description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string", "enum": sorted(FUNCTIONAL_TAGS)}},
        "suggested_new_tag": {"type": ["string", "null"]},
        "rationale": {"type": "string"},
    },
    "required": ["normalized_description", "tags", "suggested_new_tag", "rationale"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You tag Pokémon TCG cards with what they do, and return exactly one JSON object "
    "matching the given schema.\n\n"
    "Functional tags (what a card does). Search queries are parsed into these same tags with "
    "these same definitions, so apply a tag only when the card has that effect as defined here:\n"
    + render_tag_glossary()
    + """

The user message is one card's text: its name, then its Abilities, attacks or effect.

- `normalized_description`: paraphrase everything the card does in plain game vocabulary. It is \
embedded for semantic search, so describe effects, not flavour or strategy. Strip proper names \
(the card's own and any it names) and numeric magnitudes ("deal damage", not "deal 120 damage"). \
Keep energy types named inside an effect ("attach a Fire Energy"), but not the Pokémon's own type.
- `tags`: every functional tag whose definition the card's effect meets, across all of its \
attacks and Abilities. An empty array if none do (a vanilla attacker, a basic Energy).
- `suggested_new_tag`: a short kebab-case name for a distinct effect no tag above covers, or null.
- `rationale`: one or two sentences tying each tag to the card text that earns it."""
)


def _custom_id(dedupe_key: str) -> str:
    """A `dedupe_key` is normalized card text, but a Batch `custom_id` is capped at 64 chars of
    [a-zA-Z0-9_-]; its SHA-256 hex digest is exactly 64."""
    return hashlib.sha256(dedupe_key.encode()).hexdigest()


class HostedEnrichmentClient(EnrichmentClient):
    """Calls the hosted Batch model (Claude Sonnet 5.5 on Message Batches, strict structured outputs).

    No `temperature` (Sonnet 5.5 rejects a non-default one) and no forced `tool_choice`
    (also a 400); thinking stays adaptive with depth set by `_ENRICHMENT_EFFORT`.
    """

    def __init__(self, api_key: str, workspace_id: str | None = None) -> None:
        self._api_key = api_key
        # Sent as `anthropic-workspace-id`; only needed for a key not scoped to a workspace.
        self._headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None

    def _client(self) -> AsyncAnthropic:
        return AsyncAnthropic(api_key=self._api_key, default_headers=self._headers)

    async def submit_batch(self, requests: list[EnrichmentRequest]) -> str:
        # One shared, byte-identical system block, so every request in the batch reads the
        # same cached prefix. A batch can take far longer than 5 minutes, hence the 1h TTL.
        system: list[TextBlockParam] = [
            {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral", "ttl": "1h"}}
        ]
        batch_requests = [
            Request(
                custom_id=_custom_id(request.dedupe_key),
                params=MessageCreateParamsNonStreaming(
                    model=_ENRICHMENT_MODEL,
                    max_tokens=_MAX_TOKENS,
                    thinking={"type": "adaptive"},
                    output_config={
                        "effort": _ENRICHMENT_EFFORT,
                        "format": {"type": "json_schema", "schema": ENRICHMENT_JSON_SCHEMA},
                    },
                    system=system,
                    messages=[{"role": "user", "content": request.canonical_card_text}],
                ),
            )
            for request in requests
        ]
        async with self._client() as client:
            batch = await client.messages.batches.create(requests=batch_requests)
        return batch.id

    async def poll_batch(self, batch_id: str) -> str:
        # A batch only ever ends (`in_progress` -> `canceling` -> `ended`); a failure is
        # per request, so it surfaces in `fetch_results` rather than as status.FAILED here.
        async with self._client() as client:
            batch = await client.messages.batches.retrieve(batch_id)
        return status.COMPLETED if batch.processing_status == "ended" else status.PENDING

    async def fetch_results(self, batch_id: str, dedupe_keys: list[str]) -> list[EnrichmentResult]:
        dedupe_key_by_custom_id = {_custom_id(dedupe_key): dedupe_key for dedupe_key in dedupe_keys}
        results = []
        async with self._client() as client:
            async for response in await client.messages.batches.results(batch_id):
                dedupe_key = dedupe_key_by_custom_id.get(response.custom_id)
                # errored / expired / canceled: no answer, so leave the card out and let the
                # pipeline put it back up for the next submit.
                if dedupe_key is None or response.result.type != "succeeded":
                    continue
                results.append(_to_result(dedupe_key, response.result.message))
        return results


def _to_result(dedupe_key: str, message: Message) -> EnrichmentResult:
    """A refused, truncated or unparseable answer becomes an empty result, which the
    refusal-first validator routes to the repair path. Server-side refusal fallbacks
    aren't available on Batches."""
    if message.stop_reason in ("refusal", "max_tokens"):
        return EnrichmentResult(dedupe_key=dedupe_key)
    text = next((block.text for block in message.content if block.type == "text"), "")
    try:
        output = json.loads(text)
        return EnrichmentResult(
            dedupe_key=dedupe_key,
            normalized_description=output["normalized_description"],
            tags=output["tags"],
            suggested_new_tag=output["suggested_new_tag"],
            rationale=output["rationale"],
        )
    # Strict outputs should rule these out, but one bad answer must not sink the whole fetch.
    except (json.JSONDecodeError, KeyError, TypeError):
        return EnrichmentResult(dedupe_key=dedupe_key)
