"""The runner: builds the real catalog by chaining ingest → tagging → embedding.

`scripts/build_catalog.py` is the hand-run command around it. Every step is idempotent, so a
re-run (including one after a crash) only does what is still left to do.
"""

import asyncio
import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field

from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.included_sets import INCLUDED_SETS
from app.catalog.ingest import run_ingest
from app.catalog.models import Card
from app.catalog.overrides import CatalogOverrides, OverrideCheck
from app.clients.catalog_client import CatalogClient
from app.clients.embedding_client import EmbeddingClient
from app.clients.enrichment_client import EnrichmentClient
from app.enrichment import status
from app.enrichment.embedding import EmbeddingPassReport, run_embedding_pass
from app.enrichment.models import CardEnrichment
from app.enrichment.pipeline import poll_and_apply_batch, submit_enrichment_batch
from app.enrichment.queries import InFlightBatch, get_in_flight_batches
from app.enrichment.taxonomy import PROMPT_VERSION, TAXONOMY_VERSION

# Since #115 a re-tagged card has no vector until the embedding step, and semantic search only
# ranks cards with a current vector. The app and the runner read the same version constants,
# so deploy order can't hide the gap; only finishing this run closes it.
REMINDER_AFTER_SUBMIT = (
    "Reminder: concept search returns nothing for these cards until this run finishes. "
    "Semantic-only queries come back empty for them and mixed queries rank them by tags only; "
    "filtering and browsing are unaffected. The routine is: bump the version, then run the runner "
    "straight away, and let it finish."
)

type Say = Callable[[str], None]


@dataclass(frozen=True)
class RunReport:
    """What one run did, step by step."""

    printings_ingested: dict[str, int]
    """Set id → its printings in the catalog after ingest."""
    override_report: list[OverrideCheck]
    submitted: dict[str, int]
    """Batch id → card entities staked out under it, for each batch this run submitted."""
    batch_statuses: dict[str, str]
    """Batch id → how it ended, for every batch this run polled (including a crashed run's)."""
    embedding: EmbeddingPassReport
    missing_printing_ids: list[str] = field(default_factory=list)
    """Printing ids asked for that TCGdex didn't return, so weren't ingested."""


async def run_catalog_build(
    session: AsyncSession,
    catalog_client: CatalogClient,
    enrichment_client: EnrichmentClient,
    embedding_client: EmbeddingClient,
    *,
    set_ids: Sequence[str] = INCLUDED_SETS,
    printing_ids: Collection[str] | None = None,
    overrides: CatalogOverrides | None = None,
    poll_interval_seconds: float = 60,
    say: Say = print,
) -> RunReport:
    """Ingest `set_ids`, tag every entity that is due, wait for the batches, then embed.

    `printing_ids` limits the run to those printings' sets, and tagging and embedding to their
    card entities. Every printing must belong to one of `set_ids`. `overrides` defaults to the
    hand-kept Catalog overrides file. Progress and a summary of each step go to `say`.
    """
    if printing_ids is not None:
        set_ids = sets_of_printings(printing_ids, set_ids)

    say(f"1. Ingest ({len(set_ids)} sets)")
    printings_ingested: dict[str, int] = {}
    override_report: list[OverrideCheck] = []
    for set_id in set_ids:
        override_report.extend(await run_ingest(session, catalog_client, set_id, overrides=overrides))
        printings_ingested[set_id] = await session.scalar(
            select(func.count()).select_from(Card).where(Card.set_id == set_id)
        ) or 0
        say(f"   {set_id}: {printings_ingested[set_id]} printings")
    _say_override_report(override_report, say)

    dedupe_keys: set[str] | None = None
    missing_printing_ids: list[str] = []
    if printing_ids is not None:
        rows = await session.execute(select(Card.id, Card.dedupe_key).where(Card.id.in_(printing_ids)))
        found = {row.id: row.dedupe_key for row in rows}
        dedupe_keys = set(found.values())
        missing_printing_ids = sorted(set(printing_ids) - set(found))
        say(f"   Limited to {len(found)} printings ({len(dedupe_keys)} card entities)")
        if missing_printing_ids:
            say(f"   Not returned by TCGdex: {', '.join(missing_printing_ids)}")

    batch_statuses: dict[str, str] = {}
    # A crashed run's batch is seen to the end first. Its rows may carry a stamp from before a
    # version bump, and an ordinary submit would re-stake them and pay for them twice.
    if crashed_runs_batches := await get_in_flight_batches(session):
        say("   Finishing the batches a previous run left in flight")
        batch_statuses |= await _poll_until_done(
            session, enrichment_client, crashed_runs_batches, poll_interval_seconds, say
        )

    say("2. Submit tagging")
    # New, changed or failed entities first; then the needs_repair ones, which an ordinary
    # submit leaves alone. A card in the first batch is no longer needs_repair, so none is sent twice.
    submitted: dict[str, int] = {}
    for repair_only in (False, True):
        batch_id = await submit_enrichment_batch(
            session, enrichment_client, repair_only=repair_only, dedupe_keys=dedupe_keys
        )
        if batch_id is not None:
            submitted[batch_id] = await _count_staked(session, batch_id)
            kind = "needs_repair card entities" if repair_only else "new, changed or failed card entities"
            say(f"   Submitted {batch_id}: {submitted[batch_id]} {kind}")
    if submitted:
        say(f"   {REMINDER_AFTER_SUBMIT}")
    else:
        say("   Nothing to tag")

    say("3. Poll and apply")
    new_batches = [InFlightBatch(batch_id, TAXONOMY_VERSION, PROMPT_VERSION) for batch_id in submitted]
    batch_statuses |= await _poll_until_done(session, enrichment_client, new_batches, poll_interval_seconds, say)
    for batch_id, batch_status in batch_statuses.items():
        say(f"   {batch_id}: {batch_status}")
    await _say_tagging_outcome(session, dedupe_keys, say)

    say("4. Embed")
    embedding = await run_embedding_pass(session, embedding_client, dedupe_keys=dedupe_keys)
    say(
        f"   Embedded {embedding.embedded}; {embedding.skipped} left unembedded "
        "(no normalized description: pending, failed or needs_repair)"
    )

    return RunReport(
        printings_ingested=printings_ingested,
        override_report=override_report,
        submitted=submitted,
        batch_statuses=batch_statuses,
        embedding=embedding,
        missing_printing_ids=missing_printing_ids,
    )


def sets_of_printings(printing_ids: Collection[str], set_ids: Sequence[str]) -> list[str]:
    """The sets in `set_ids` that the printings belong to, in `set_ids` order.

    A printing id is `<set id>-<local id>`, and set ids can themselves contain `-` (`30th-c`),
    so a printing belongs to the longest set id it starts with. Raises `ValueError` naming
    every printing that belongs to none of them.
    """
    wanted: set[str] = set()
    unmatched: list[str] = []
    for printing_id in printing_ids:
        candidates = [set_id for set_id in set_ids if printing_id.startswith(f"{set_id}-")]
        if candidates:
            wanted.add(max(candidates, key=len))
        else:
            unmatched.append(printing_id)
    if unmatched:
        raise ValueError(f"Not in any of the sets being run: {', '.join(sorted(unmatched))}")
    return [set_id for set_id in set_ids if set_id in wanted]


def _say_override_report(report: list[OverrideCheck], say: Say) -> None:
    if not report:
        say("   Catalog overrides: none that TCGdex now supplies")
        return
    say(f"   Catalog overrides whose field TCGdex now supplies ({len(report)}):")
    for check in report:
        advice = "redundant, delete it" if check.status == "same" else "review: keep it, or delete it to use TCGdex's"
        say(f"     {check.printing_id} {check.field}: {check.status} ({advice})")
        if check.status == "differs":
            say(f"       override: {check.override_value!r}")
            say(f"       TCGdex:   {check.tcgdex_value!r}")


async def _say_tagging_outcome(session: AsyncSession, dedupe_keys: Collection[str] | None, say: Say) -> None:
    """Card entities per enrichment status, then the failed and needs_repair ones by a printing each."""
    in_scope = CardEnrichment.dedupe_key.in_(dedupe_keys) if dedupe_keys is not None else true()

    counts = await session.execute(
        select(CardEnrichment.status, func.count()).where(in_scope).group_by(CardEnrichment.status)
    )
    say("   Card entities by status: " + (", ".join(f"{row[0]} {row[1]}" for row in sorted(counts)) or "none"))

    untagged = await session.execute(
        select(Card.id, Card.name, CardEnrichment.status)
        .join(CardEnrichment, CardEnrichment.dedupe_key == Card.dedupe_key)
        .where(in_scope, CardEnrichment.status.in_((status.NEEDS_REPAIR, status.FAILED)))
        .distinct(Card.dedupe_key)
        .order_by(Card.dedupe_key, Card.id)
    )
    rows = sorted(untagged, key=lambda row: (row.status, row.id))
    for row in rows:
        say(f"   {row.status}: {row.id} {row.name}")
    if any(row.status == status.NEEDS_REPAIR for row in rows):
        say("   needs_repair cards are re-tagged on the next run")
    if any(row.status == status.FAILED for row in rows):
        say("   failed cards are resubmitted on the next run")


async def _count_staked(session: AsyncSession, batch_id: str) -> int:
    return await session.scalar(
        select(func.count())
        .select_from(CardEnrichment)
        .where(CardEnrichment.batch_id == batch_id, CardEnrichment.status == status.PENDING)
    ) or 0


async def _poll_until_done(
    session: AsyncSession,
    enrichment_client: EnrichmentClient,
    batches: list[InFlightBatch],
    poll_interval_seconds: float,
    say: Say,
) -> dict[str, str]:
    """Polls each batch until it leaves `pending`, applying its results under its own stamp."""
    started = time.monotonic()
    ended: dict[str, str] = {}
    waiting = list(batches)
    while waiting:
        for batch in list(waiting):
            batch_status = await poll_and_apply_batch(
                session,
                enrichment_client,
                batch.batch_id,
                taxonomy_version=batch.taxonomy_version,
                prompt_version=batch.prompt_version,
            )
            if batch_status != status.PENDING:
                ended[batch.batch_id] = batch_status
                waiting.remove(batch)
        if waiting:
            still = ", ".join(batch.batch_id for batch in waiting)
            say(f"   Still processing after {time.monotonic() - started:.0f}s: {still}")
            await asyncio.sleep(poll_interval_seconds)
    return ended
