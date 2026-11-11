from datetime import date
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.identity import build_card_identity
from app.catalog.ingest import run_ingest
from app.clients.catalog_client import SetSnapshot
from app.clients.enrichment_client import EnrichmentResult
from app.enrichment import status
from app.enrichment.models import CardEnrichment
from app.enrichment.pipeline import submit_enrichment_batch
from app.enrichment.taxonomy import PROMPT_VERSION, TAXONOMY_VERSION
from app.runner import REMINDER_AFTER_SUBMIT, RunReport, run_catalog_build
from tests.stubs import StubCatalogClient, StubEmbeddingClient, StubEnrichmentClient


def _pokemon(printing_id: str, name: str, effect: str) -> dict:
    return {
        "id": printing_id,
        "localId": printing_id.rsplit("-", 1)[1],
        "name": name,
        "category": "Pokemon",
        "hp": 70,
        "types": ["Fire"],
        "stage": "Basic",
        "regulationMark": "H",
        "attacks": [{"name": "Burn", "cost": ["Fire"], "damage": 30, "effect": effect}],
        "abilities": [],
    }


_CHARMANDER = _pokemon("sv01-004", "Charmander", "Discard an Energy from this Pokémon.")
_VULPIX = _pokemon("sv01-012", "Vulpix", "Draw a card.")
_GROWLITHE = _pokemon("sv02-020", "Growlithe", "Search your deck for a Fire Energy.")

_SNAPSHOTS = {
    "sv01": SetSnapshot("sv01", date(2023, 3, 31), [_CHARMANDER, _VULPIX], name="Scarlet & Violet"),
    "sv02": SetSnapshot("sv02", date(2023, 6, 9), [_GROWLITHE], name="Paldea Evolved"),
}


def _key(raw: dict) -> str:
    return build_card_identity(raw).dedupe_key


def _answer(raw: dict, *, description: str = "Does a thing.") -> EnrichmentResult:
    return EnrichmentResult(dedupe_key=_key(raw), normalized_description=description, tags=["draw"])


_ANSWERS = {_key(raw): _answer(raw) for raw in (_CHARMANDER, _VULPIX, _GROWLITHE)}


async def _run(session: AsyncSession, enrichment_client: StubEnrichmentClient, **kwargs: Any) -> RunReport:
    return await run_catalog_build(
        session,
        StubCatalogClient(_SNAPSHOTS),
        enrichment_client,
        StubEmbeddingClient(),
        **{
            "set_ids": list(_SNAPSHOTS),
            "overrides": {},
            "poll_interval_seconds": 0,
            "say": lambda _line: None,
            **kwargs,
        },
    )


async def _enrichments(session: AsyncSession) -> dict[str, CardEnrichment]:
    session.expire_all()
    return {row.dedupe_key: row for row in await session.scalars(select(CardEnrichment))}


async def test_a_run_tags_and_embeds_every_entity_in_the_given_sets(db_session: AsyncSession) -> None:
    report = await _run(db_session, StubEnrichmentClient(_ANSWERS))

    rows = await _enrichments(db_session)
    assert set(rows) == {_key(_CHARMANDER), _key(_VULPIX), _key(_GROWLITHE)}
    assert all(row.status == status.COMPLETED and row.vector is not None for row in rows.values())
    assert report.printings_ingested == {"sv01": 2, "sv02": 1}
    assert report.submitted == {"batch-1": 3}
    assert report.embedding.embedded == 3


async def test_re_running_on_an_unchanged_catalog_tags_and_embeds_nothing(db_session: AsyncSession) -> None:
    enrichment_client = StubEnrichmentClient(_ANSWERS)
    await _run(db_session, enrichment_client)

    report = await _run(db_session, enrichment_client)

    assert report.submitted == {}
    assert report.embedding.embedded == 0


async def test_a_re_run_re_tags_only_changed_text_and_needs_repair_cards(db_session: AsyncSession) -> None:
    refusal = EnrichmentResult(dedupe_key=_key(_VULPIX), normalized_description="")
    await _run(db_session, StubEnrichmentClient({**_ANSWERS, _key(_VULPIX): refusal}))
    assert (await _enrichments(db_session))[_key(_VULPIX)].status == status.NEEDS_REPAIR

    reworded = {**_CHARMANDER, "attacks": [{**_CHARMANDER["attacks"][0], "effect": "Discard 2 Energy."}]}
    snapshots = {**_SNAPSHOTS, "sv01": SetSnapshot("sv01", date(2023, 3, 31), [reworded, _VULPIX])}
    enrichment_client = StubEnrichmentClient({**_ANSWERS, _key(reworded): _answer(reworded)})
    report = await run_catalog_build(
        db_session,
        StubCatalogClient(snapshots),
        enrichment_client,
        StubEmbeddingClient(),
        set_ids=list(snapshots),
        poll_interval_seconds=0,
        say=lambda _line: None,
    )

    assert sum(report.submitted.values()) == 2
    rows = await _enrichments(db_session)
    assert rows[_key(reworded)].status == status.COMPLETED
    assert rows[_key(_VULPIX)].status == status.COMPLETED
    assert report.embedding.embedded == 2


async def test_a_re_run_after_a_crash_applies_the_batch_still_in_flight(db_session: AsyncSession) -> None:
    enrichment_client = StubEnrichmentClient(_ANSWERS)
    for set_id in _SNAPSHOTS:
        await run_ingest(db_session, StubCatalogClient(_SNAPSHOTS), set_id)
    # The crashed run got as far as submitting; nothing polled the batch afterwards.
    await submit_enrichment_batch(db_session, enrichment_client)

    report = await _run(db_session, enrichment_client)

    assert report.submitted == {}
    assert report.batch_statuses == {"batch-1": status.COMPLETED}
    rows = await _enrichments(db_session)
    assert all(row.status == status.COMPLETED and row.vector is not None for row in rows.values())


async def test_printing_ids_limit_the_run_to_those_printings_sets_and_entities(db_session: AsyncSession) -> None:
    # Already in the catalog from an earlier run: Growlithe untagged, Vulpix tagged but not embedded.
    for set_id in _SNAPSHOTS:
        await run_ingest(db_session, StubCatalogClient(_SNAPSHOTS), set_id)
    db_session.add(
        CardEnrichment(
            dedupe_key=_key(_VULPIX),
            normalized_description="Draws a card.",
            taxonomy_version=TAXONOMY_VERSION,
            prompt_version=PROMPT_VERSION,
            status=status.COMPLETED,
        )
    )
    await db_session.commit()

    report = await _run(db_session, StubEnrichmentClient(_ANSWERS), printing_ids=["sv01-004", "sv01-999"])

    assert report.printings_ingested == {"sv01": 2}
    assert report.missing_printing_ids == ["sv01-999"]
    assert report.submitted == {"batch-1": 1}
    rows = await _enrichments(db_session)
    assert rows[_key(_CHARMANDER)].vector is not None
    assert _key(_GROWLITHE) not in rows
    assert rows[_key(_VULPIX)].vector is None


async def test_a_printing_id_outside_the_given_sets_is_refused(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="me06-001"):
        await _run(db_session, StubEnrichmentClient(_ANSWERS), printing_ids=["sv01-004", "me06-001"])


async def test_submitting_a_batch_prints_the_concept_search_reminder(db_session: AsyncSession) -> None:
    lines: list[str] = []
    enrichment_client = StubEnrichmentClient(_ANSWERS)
    await _run(db_session, enrichment_client, say=lines.append)
    assert any(REMINDER_AFTER_SUBMIT in line for line in lines)

    lines.clear()
    await _run(db_session, enrichment_client, say=lines.append)
    assert not any(REMINDER_AFTER_SUBMIT in line for line in lines)


async def test_the_output_lists_the_override_report_and_the_cards_needing_repair(db_session: AsyncSession) -> None:
    lines: list[str] = []
    refusal = EnrichmentResult(dedupe_key=_key(_VULPIX), normalized_description="")
    await _run(
        db_session,
        StubEnrichmentClient({**_ANSWERS, _key(_VULPIX): refusal}),
        overrides={"sv02-020": {"name": "Growlithe"}, "sv01-004": {"name": "Charmeleon"}},
        say=lines.append,
    )

    output = "\n".join(lines)
    assert "sv02-020 name: same" in output
    assert "sv01-004 name: differs" in output
    assert "sv01-012 Vulpix" in output


async def test_the_run_waits_for_a_batch_that_is_still_processing(db_session: AsyncSession) -> None:
    class SlowEnrichmentClient(StubEnrichmentClient):
        polls = 0

        async def poll_batch(self, batch_id: str) -> str:
            self.polls += 1
            return status.PENDING if self.polls < 3 else await super().poll_batch(batch_id)

    enrichment_client = SlowEnrichmentClient(_ANSWERS)
    report = await _run(db_session, enrichment_client)

    assert enrichment_client.polls == 3
    assert report.batch_statuses == {"batch-1": status.COMPLETED}
    assert report.embedding.embedded == 3
