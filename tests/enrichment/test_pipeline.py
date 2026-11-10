from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.identity import build_card_identity
from app.catalog.ingest import run_ingest
from app.clients.catalog_client import SetSnapshot
from app.clients.enrichment_client import EnrichmentResult
from app.enrichment import status
from app.enrichment.models import CardEnrichment
from app.enrichment.pipeline import poll_and_apply_batch, submit_enrichment_batch
from tests.stubs import StubCatalogClient, StubEnrichmentClient

_CHARIZARD = {
    "id": "base1-4",
    "localId": "4",
    "name": "Charizard",
    "category": "Pokemon",
    "hp": 120,
    "types": ["Fire"],
    "stage": "Stage 2",
    "regulationMark": "D",
    "attacks": [{"name": "Fire Spin", "cost": ["Fire"], "damage": 100, "effect": "Discard 2 Energy and draw a card."}],
    "abilities": [],
}

_CHARIZARD_KEY = build_card_identity(_CHARIZARD).dedupe_key


async def _ingest_charizard(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient({"base1": SetSnapshot("base1", date(1999, 1, 9), [_CHARIZARD])})
    await run_ingest(db_session, catalog_client, "base1")


async def test_submit_stakes_out_pending_rows_and_returns_a_batch_id(db_session: AsyncSession) -> None:
    await _ingest_charizard(db_session)
    enrichment_client = StubEnrichmentClient({})

    batch_id = await submit_enrichment_batch(db_session, enrichment_client)

    assert batch_id == "batch-1"
    row = await db_session.scalar(select(CardEnrichment).where(CardEnrichment.dedupe_key == _CHARIZARD_KEY))
    assert row is not None
    assert row.status == status.PENDING
    assert row.batch_id == "batch-1"


async def test_submit_on_an_unchanged_corpus_is_a_no_op(db_session: AsyncSession) -> None:
    await _ingest_charizard(db_session)
    enrichment_client = StubEnrichmentClient(
        {_CHARIZARD_KEY: EnrichmentResult(dedupe_key=_CHARIZARD_KEY, normalized_description="d", tags=["recoil"])}
    )
    batch_id = await submit_enrichment_batch(db_session, enrichment_client)
    await poll_and_apply_batch(db_session, enrichment_client, batch_id)

    second_batch_id = await submit_enrichment_batch(db_session, enrichment_client)

    assert second_batch_id is None


async def test_poll_on_a_still_pending_batch_leaves_rows_untouched(db_session: AsyncSession) -> None:
    await _ingest_charizard(db_session)
    enrichment_client = StubEnrichmentClient({}, pending_batch_ids={"batch-1"})
    batch_id = await submit_enrichment_batch(db_session, enrichment_client)

    result_status = await poll_and_apply_batch(db_session, enrichment_client, batch_id)

    assert result_status == status.PENDING
    row = await db_session.scalar(select(CardEnrichment).where(CardEnrichment.dedupe_key == _CHARIZARD_KEY))
    assert row is not None and row.status == status.PENDING


async def test_poll_on_a_completed_batch_applies_valid_results(db_session: AsyncSession) -> None:
    await _ingest_charizard(db_session)
    enrichment_client = StubEnrichmentClient(
        {
            _CHARIZARD_KEY: EnrichmentResult(
                dedupe_key=_CHARIZARD_KEY,
                normalized_description="Discard energy from this Pokemon and draw a card.",
                tags=["recoil", "draw"],
                rationale="Attack costs Energy and nets a draw.",
            )
        }
    )
    batch_id = await submit_enrichment_batch(db_session, enrichment_client)

    result_status = await poll_and_apply_batch(db_session, enrichment_client, batch_id)

    assert result_status == status.COMPLETED
    row = await db_session.scalar(select(CardEnrichment).where(CardEnrichment.dedupe_key == _CHARIZARD_KEY))
    assert row is not None
    assert row.status == status.COMPLETED
    assert row.tags == ["recoil", "draw"]
    assert row.normalized_description == "Discard energy from this Pokemon and draw a card."


async def test_poll_on_a_failed_batch_marks_rows_failed_and_they_become_eligible_for_resubmission(
    db_session: AsyncSession,
) -> None:
    await _ingest_charizard(db_session)
    enrichment_client = StubEnrichmentClient({}, failed_batch_ids={"batch-1"})
    batch_id = await submit_enrichment_batch(db_session, enrichment_client)

    result_status = await poll_and_apply_batch(db_session, enrichment_client, batch_id)
    assert result_status == status.FAILED

    row = await db_session.scalar(select(CardEnrichment).where(CardEnrichment.dedupe_key == _CHARIZARD_KEY))
    assert row is not None and row.status == status.FAILED

    retry_client = StubEnrichmentClient(
        {_CHARIZARD_KEY: EnrichmentResult(dedupe_key=_CHARIZARD_KEY, normalized_description="d", tags=[])}
    )
    retry_batch_id = await submit_enrichment_batch(db_session, retry_client)
    assert retry_batch_id is not None


async def test_a_refusal_is_applied_as_needs_repair_and_is_not_resubmitted(db_session: AsyncSession) -> None:
    await _ingest_charizard(db_session)
    enrichment_client = StubEnrichmentClient({_CHARIZARD_KEY: EnrichmentResult(dedupe_key=_CHARIZARD_KEY)})
    batch_id = await submit_enrichment_batch(db_session, enrichment_client)
    await poll_and_apply_batch(db_session, enrichment_client, batch_id)

    row = await db_session.scalar(select(CardEnrichment).where(CardEnrichment.dedupe_key == _CHARIZARD_KEY))
    assert row is not None and row.status == status.NEEDS_REPAIR
    assert row.normalized_description is None

    next_batch_id = await submit_enrichment_batch(db_session, enrichment_client)
    assert next_batch_id is None


async def test_a_card_the_batch_never_answered_is_marked_failed_and_resubmitted(db_session: AsyncSession) -> None:
    # A request that errored, expired or was canceled comes back with no result. Left
    # `pending`, it would never be resubmitted.
    await _ingest_charizard(db_session)
    enrichment_client = StubEnrichmentClient({})
    batch_id = await submit_enrichment_batch(db_session, enrichment_client)

    result_status = await poll_and_apply_batch(db_session, enrichment_client, batch_id)

    assert result_status == status.COMPLETED
    row = await db_session.scalar(select(CardEnrichment).where(CardEnrichment.dedupe_key == _CHARIZARD_KEY))
    assert row is not None and row.status == status.FAILED
    assert await submit_enrichment_batch(db_session, enrichment_client) is not None


_BLASTOISE = {
    **_CHARIZARD,
    "id": "base1-2",
    "localId": "2",
    "name": "Blastoise",
    "types": ["Water"],
    "attacks": [{"name": "Hydro Pump", "cost": ["Water"], "damage": 40, "effect": "Does more damage for extra Water Energy."}],
}
_BLASTOISE_KEY = build_card_identity(_BLASTOISE).dedupe_key


async def test_a_repair_only_submission_re_tags_just_the_needs_repair_cards(db_session: AsyncSession) -> None:
    await _ingest_charizard(db_session)
    refusing_client = StubEnrichmentClient({_CHARIZARD_KEY: EnrichmentResult(dedupe_key=_CHARIZARD_KEY)})
    first_batch_id = await submit_enrichment_batch(db_session, refusing_client)
    assert first_batch_id is not None
    await poll_and_apply_batch(db_session, refusing_client, first_batch_id)
    # A card new since that run is due ordinary enrichment, not repair.
    catalog_client = StubCatalogClient({"base1": SetSnapshot("base1", date(1999, 1, 9), [_CHARIZARD, _BLASTOISE])})
    await run_ingest(db_session, catalog_client, "base1")

    repair_client = StubEnrichmentClient(
        {
            _CHARIZARD_KEY: EnrichmentResult(
                dedupe_key=_CHARIZARD_KEY, normalized_description="Discard energy and draw a card.", tags=["draw"]
            )
        }
    )
    batch_id = await submit_enrichment_batch(db_session, repair_client, repair_only=True)
    assert batch_id is not None
    await poll_and_apply_batch(db_session, repair_client, batch_id)

    charizard = await db_session.scalar(select(CardEnrichment).where(CardEnrichment.dedupe_key == _CHARIZARD_KEY))
    assert charizard is not None
    assert charizard.status == status.COMPLETED
    assert charizard.normalized_description == "Discard energy and draw a card."
    blastoise = await db_session.scalar(select(CardEnrichment).where(CardEnrichment.dedupe_key == _BLASTOISE_KEY))
    assert blastoise is None


async def test_a_repair_only_submission_with_nothing_to_repair_is_a_no_op(db_session: AsyncSession) -> None:
    await _ingest_charizard(db_session)

    batch_id = await submit_enrichment_batch(db_session, StubEnrichmentClient({}), repair_only=True)

    assert batch_id is None
