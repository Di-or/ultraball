from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.identity import build_card_identity
from app.catalog.ingest import run_ingest
from app.clients.catalog_client import SetSnapshot
from app.enrichment import status
from app.enrichment.models import CardEnrichment
from app.enrichment.queries import get_cards_pending_enrichment
from tests.stubs import StubCatalogClient

_CHARIZARD = {
    "id": "base1-4",
    "localId": "4",
    "name": "Charizard",
    "category": "Pokemon",
    "hp": 120,
    "types": ["Fire"],
    "stage": "Stage 2",
    "regulationMark": "D",
    "attacks": [{"name": "Fire Spin", "cost": ["Fire"], "damage": 100, "effect": "Discard 2 Energy."}],
    "abilities": [],
}

_PIKACHU = {
    "id": "base1-58",
    "localId": "58",
    "name": "Pikachu",
    "category": "Pokemon",
    "hp": 60,
    "types": ["Lightning"],
    "stage": "Basic",
    "regulationMark": "D",
    "attacks": [{"name": "Gnaw", "cost": ["Colorless"], "damage": 10, "effect": ""}],
    "abilities": [],
}


async def test_a_new_dedupe_key_with_no_row_is_pending(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient({"base1": SetSnapshot("base1", date(1999, 1, 9), [_CHARIZARD])})
    await run_ingest(db_session, catalog_client, "base1")

    pending = await get_cards_pending_enrichment(db_session, taxonomy_version="v1", prompt_version="v1")

    identity = build_card_identity(_CHARIZARD)
    assert pending == [(identity.dedupe_key, identity.canonical_card_text)]


async def test_an_unchanged_corpus_with_a_completed_row_is_a_no_op(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient({"base1": SetSnapshot("base1", date(1999, 1, 9), [_CHARIZARD, _PIKACHU])})
    await run_ingest(db_session, catalog_client, "base1")

    pending_before = await get_cards_pending_enrichment(db_session, taxonomy_version="v1", prompt_version="v1")
    assert len(pending_before) == 2

    for dedupe_key, _ in pending_before:
        db_session.add(
            CardEnrichment(
                dedupe_key=dedupe_key,
                normalized_description="desc",
                tags=[],
                taxonomy_version="v1",
                prompt_version="v1",
                status=status.COMPLETED,
                batch_id="batch-1",
            )
        )
    await db_session.commit()

    pending_after = await get_cards_pending_enrichment(db_session, taxonomy_version="v1", prompt_version="v1")
    assert pending_after == []


async def test_a_taxonomy_version_bump_forces_a_re_pass(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient({"base1": SetSnapshot("base1", date(1999, 1, 9), [_CHARIZARD])})
    await run_ingest(db_session, catalog_client, "base1")

    [(dedupe_key, _)] = await get_cards_pending_enrichment(db_session, taxonomy_version="v1", prompt_version="v1")
    db_session.add(
        CardEnrichment(
            dedupe_key=dedupe_key,
            normalized_description="desc",
            tags=[],
            taxonomy_version="v1",
            prompt_version="v1",
            status=status.COMPLETED,
            batch_id="batch-1",
        )
    )
    await db_session.commit()

    pending_v2 = await get_cards_pending_enrichment(db_session, taxonomy_version="v2", prompt_version="v1")

    assert [key for key, _ in pending_v2] == [dedupe_key]


async def test_a_failed_row_is_retried_but_a_needs_repair_row_is_not(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient({"base1": SetSnapshot("base1", date(1999, 1, 9), [_CHARIZARD, _PIKACHU])})
    await run_ingest(db_session, catalog_client, "base1")
    [(failed_key, _), (repair_key, _)] = await get_cards_pending_enrichment(
        db_session, taxonomy_version="v1", prompt_version="v1"
    )

    db_session.add(
        CardEnrichment(
            dedupe_key=failed_key, taxonomy_version="v1", prompt_version="v1", status=status.FAILED, batch_id="batch-1"
        )
    )
    db_session.add(
        CardEnrichment(
            dedupe_key=repair_key,
            taxonomy_version="v1",
            prompt_version="v1",
            status=status.NEEDS_REPAIR,
            batch_id="batch-1",
        )
    )
    await db_session.commit()

    pending = await get_cards_pending_enrichment(db_session, taxonomy_version="v1", prompt_version="v1")

    assert [key for key, _ in pending] == [failed_key]


async def test_a_pending_row_is_not_resubmitted(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient({"base1": SetSnapshot("base1", date(1999, 1, 9), [_CHARIZARD])})
    await run_ingest(db_session, catalog_client, "base1")
    [(dedupe_key, _)] = await get_cards_pending_enrichment(db_session, taxonomy_version="v1", prompt_version="v1")

    db_session.add(
        CardEnrichment(
            dedupe_key=dedupe_key, taxonomy_version="v1", prompt_version="v1", status=status.PENDING, batch_id="batch-1"
        )
    )
    await db_session.commit()

    pending = await get_cards_pending_enrichment(db_session, taxonomy_version="v1", prompt_version="v1")

    assert pending == []
