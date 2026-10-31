"""Enrich a handful of real cards against the hosted Batch model, and print tags, tokens and cost.

Run by hand: `uv run python -m scripts.enrich_sample [card_id ...]`. Not part of the app, and
it spends real money: ANTHROPIC_API_KEY (or CLAUDE_API_KEY) needs Console credits. A Claude
Pro subscription doesn't cover API calls.

Cards come straight from TCGdex and skip Postgres; the request is exactly what the pipeline
submits (`HostedEnrichmentClient`). Batches usually end within minutes, but can take up to 24h.
"""

import argparse
import asyncio
import io
import sys
import time

import anthropic
import httpx

from app.catalog.identity import build_card_identity
from app.clients.enrichment_client import EnrichmentRequest, HostedEnrichmentClient
from app.config import Settings
from app.enrichment import status
from app.enrichment.validation import validate_enrichment_result

# Well-known Scarlet & Violet cards, none of them a prompt example (app.enrichment.taxonomy).
_DEFAULT_CARD_IDS = ["sv06-130", "sv03-125", "sv01-086", "sv02-185", "sv04-160"]
_TCGDEX_CARD_URL = "https://api.tcgdex.net/v2/en/cards/{card_id}"
_POLL_SECONDS = 30

# Claude Sonnet 5.5 per 1M tokens, at the 50% Batch discount. Cache writes at the 1h TTL
# cost 2x base input; cache reads 0.1x.
_INPUT_PER_M = 1.00
_OUTPUT_PER_M = 5.00
_CACHE_WRITE_PER_M = 2 * _INPUT_PER_M
_CACHE_READ_PER_M = 0.1 * _INPUT_PER_M


async def _fetch_requests(card_ids: list[str]) -> list[EnrichmentRequest]:
    requests = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for card_id in card_ids:
            response = await client.get(_TCGDEX_CARD_URL.format(card_id=card_id))
            response.raise_for_status()
            identity = build_card_identity(response.json())
            requests.append(EnrichmentRequest(identity.dedupe_key, identity.canonical_card_text))
    return requests


async def _usage(settings: Settings, batch_id: str) -> dict[str, int]:
    """Summed token usage across the batch's succeeded results."""
    totals = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    headers = {"anthropic-workspace-id": settings.anthropic_workspace_id} if settings.anthropic_workspace_id else None
    async with anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, default_headers=headers) as client:
        async for response in await client.messages.batches.results(batch_id):
            if response.result.type != "succeeded":
                continue
            usage = response.result.message.usage
            totals["input"] += usage.input_tokens
            totals["output"] += usage.output_tokens
            totals["cache_write"] += usage.cache_creation_input_tokens or 0
            totals["cache_read"] += usage.cache_read_input_tokens or 0
    return totals


async def main(card_ids: list[str]) -> None:
    settings = Settings()
    if not settings.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY (or CLAUDE_API_KEY) is not set")
    client = HostedEnrichmentClient(settings.anthropic_api_key, settings.anthropic_workspace_id)

    requests = await _fetch_requests(card_ids)
    batch_id = await client.submit_batch(requests)
    print(f"Submitted {batch_id} ({len(requests)} cards)", flush=True)

    started = time.monotonic()
    while await client.poll_batch(batch_id) == status.PENDING:
        print(f"  still processing after {time.monotonic() - started:.0f}s", flush=True)
        await asyncio.sleep(_POLL_SECONDS)

    results = await client.fetch_results(batch_id, [request.dedupe_key for request in requests])
    by_key = {result.dedupe_key: result for result in results}
    for card_id, request in zip(card_ids, requests):
        result = by_key.get(request.dedupe_key)
        name = request.canonical_card_text.splitlines()[0]
        if result is None:
            print(f"\n{card_id} {name}: no answer (would be marked failed and retried)")
            continue
        validated = validate_enrichment_result(result)
        print(f"\n{card_id} {name}: {validated.status}")
        print(f"  tags: {', '.join(result.tags) or '(none)'}")
        print(f"  suggested_new_tag: {result.suggested_new_tag}")
        print(f"  description: {result.normalized_description}")
        print(f"  rationale: {result.rationale}")

    usage = await _usage(settings, batch_id)
    cost = (
        usage["input"] * _INPUT_PER_M
        + usage["output"] * _OUTPUT_PER_M
        + usage["cache_write"] * _CACHE_WRITE_PER_M
        + usage["cache_read"] * _CACHE_READ_PER_M
    ) / 1_000_000
    print(f"\nTokens: {usage}")
    print(f"Cost: ${cost:.4f} (${cost / len(requests):.4f} per card), {time.monotonic() - started:.0f}s")


if __name__ == "__main__":
    # Card text uses non-ASCII (é); Windows consoles default to a legacy code page.
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    parser = argparse.ArgumentParser(description="Enrich a handful of real cards against the hosted Batch model.")
    parser.add_argument("card_ids", nargs="*", default=_DEFAULT_CARD_IDS)
    asyncio.run(main(parser.parse_args().card_ids))
