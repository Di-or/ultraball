"""Build the real catalog: ingest the Included sets, tag, then embed.

Run by hand, in its own terminal and not inside an agent session (an earlier trial was
stopped for low memory inside one):

    uv run python -m scripts.build_catalog
    uv run python -m scripts.build_catalog --printings sv06.5-047 sv01-196
    uv run python -m scripts.build_catalog --printings-file trial-printings.txt

Steps: (1) ingest every Included set (`app/catalog/included_sets.py`) from TCGdex, remove any
printings of the excluded sets, and print the Catalog override report; (2) submit tagging
batches for new, changed, failed and needs_repair card entities; (3) poll until they end and
apply them; (4) run the embedding pass. Every step is idempotent, so re-running is safe and
resumes after a crash, including polling a batch that was still in flight.

It spends real money and writes to DATABASE_URL (the local Postgres by default): it needs
ANTHROPIC_API_KEY (or CLAUDE_API_KEY) and VOYAGE_API_KEY. Batches usually end within minutes
to an hour, but can take up to 24h. Until the run finishes, re-tagged cards are missing from
concept search; see the README ("Building the catalog").
"""

import argparse
import asyncio
import io
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

from app.clients.catalog_client import HostedCatalogClient
from app.clients.embedding_client import HostedEmbeddingClient
from app.clients.enrichment_client import HostedEnrichmentClient
from app.config import Settings
from app.db import make_engine, make_session_factory
from app.runner import run_catalog_build
from app.schema import create_schema


def _say(line: str) -> None:
    print(line, flush=True)


async def main(printing_ids: list[str] | None, poll_seconds: float) -> None:
    settings = Settings()
    if not settings.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY (or CLAUDE_API_KEY) is not set")
    if not settings.voyage_api_key:
        raise SystemExit("VOYAGE_API_KEY is not set")

    _say(f"Database: {make_url(settings.database_url).render_as_string(hide_password=True)}")
    engine = make_engine(settings.database_url)
    try:
        await create_schema(engine)
        async with make_session_factory(engine)() as session:
            await run_catalog_build(
                session,
                HostedCatalogClient(),
                HostedEnrichmentClient(settings.anthropic_api_key, settings.anthropic_workspace_id),
                HostedEmbeddingClient(settings.voyage_api_key),
                printing_ids=printing_ids,
                poll_interval_seconds=poll_seconds,
                say=_say,
            )
    finally:
        await engine.dispose()
    _say("Done.")


def _printing_ids(args: argparse.Namespace) -> list[str] | None:
    ids = list(args.printings or [])
    if args.printings_file:
        ids.extend(Path(args.printings_file).read_text(encoding="utf-8").split())
    return ids or None


if __name__ == "__main__":
    # Card names use non-ASCII (é); Windows consoles default to a legacy code page.
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    parser = argparse.ArgumentParser(description="Ingest the Included sets, tag, then embed.")
    parser.add_argument(
        "--printings", nargs="+", metavar="PRINTING_ID", help="limit the run to these printings' sets and card entities"
    )
    parser.add_argument("--printings-file", metavar="PATH", help="like --printings, ids read from a whitespace-separated file")
    parser.add_argument("--poll-seconds", type=float, default=60, help="wait between batch polls (default 60)")
    args = parser.parse_args()
    try:
        asyncio.run(main(_printing_ids(args), args.poll_seconds))
    except ValueError as error:
        raise SystemExit(str(error)) from error
