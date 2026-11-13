"""Basic Energy is classified from card text, not TCGdex's `energyType` (issue #109).

TCGdex labels Basic Energy `energyType: "Normal"`, and labels many Special Energies `"Normal"`
too (every ME-era one, plus `sv04-266` Reversal Energy). These tests ingest real TCGdex JSON and
real-shaped printings, then drive the HTTP endpoints and enrichment submission, so every consumer
is checked against the one shared rule (CONTEXT.md: Basic Energy exception).
"""

from dataclasses import replace
from datetime import date

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.identity import build_card_identity
from app.catalog.ingest import run_ingest
from app.clients.catalog_client import SetSnapshot
from app.enrichment.models import CardEnrichment
from app.enrichment.pipeline import submit_enrichment_batch
from tests.factories import make_tcgdex_basic_energy, make_tcgdex_pokemon, make_tcgdex_special_energy
from tests.stubs import StubCatalogClient, StubEnrichmentClient
from tests.tcgdex_fixtures import fixture_snapshot, load_printing

# A Pokémon to make the decks below otherwise legal: a Basic with a current regulation mark.
_POKEMON = make_tcgdex_pokemon(id="me01-001")

# More of the real `sve` set: TCGdex names Basic Energy "<Type> Energy" and gives it no mark.
_WATER_ENERGY = make_tcgdex_basic_energy("Water", id="sve-003")

# A Basic Energy carrying a rotated mark: the Basic Energy exception still makes it legal.
_G_MARKED_GRASS_ENERGY = make_tcgdex_basic_energy("Grass", id="sve-001", regulationMark="G")

# An Energy with no effect text but a name that isn't basic: fails safe as an ordinary card.
_TEXTLESS_SPECIAL = make_tcgdex_special_energy(id="me01-130", name="Mystery Energy", effect=None)


async def _ingest(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient(
        {
            "sve": _with_cards(  # sve-002 is the real Fire Energy, `energyType: "Normal"`
                fixture_snapshot("sve", ["sve-002"]), [_WATER_ENERGY, _G_MARKED_GRASS_ENERGY]
            ),
            "me02": fixture_snapshot("me02", ["me02-124"]),  # Ignition Energy, Special but `"Normal"`
            "sv04": fixture_snapshot("sv04", ["sv04-266"]),  # Reversal Energy, Special but `"Normal"`
            "me01": SetSnapshot("me01", date(2025, 9, 26), [_POKEMON, _TEXTLESS_SPECIAL]),
            "mee": fixture_snapshot("mee"),  # the real `MEE 1`-`8`, plus MEE 12 "Basic Lightning Energy"
        }
    )
    for set_id in ("sve", "me02", "sv04", "me01", "mee"):
        await run_ingest(db_session, catalog_client, set_id)


def _with_cards(snapshot: SetSnapshot, cards: list[dict]) -> SetSnapshot:
    return replace(snapshot, cards=[*snapshot.cards, *cards])


def _dedupe_key(raw: dict) -> str:
    return build_card_identity(raw).dedupe_key


async def test_the_basic_energy_tray_returns_the_real_normal_labelled_basic_energies(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    response = await client.get("/energy/basics")

    assert response.status_code == 200
    printing_ids = [item["printing_id"] for item in response.json()["palette"]]
    assert printing_ids == [f"mee-00{n}" for n in range(1, 9)]


async def test_a_deck_with_56_basic_fire_energy_is_not_flagged(client: AsyncClient, db_session: AsyncSession) -> None:
    await _ingest(db_session)

    response = await client.post(
        "/decks/validate",
        json={"entries": [{"printing_id": "me01-001", "count": 4}, {"printing_id": "sve-002", "count": 56}]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["violations"] == []
    assert body["legal"] is True


async def test_basic_energy_with_a_rotated_mark_is_standard_legal_in_a_deck(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    response = await client.post(
        "/decks/validate",
        json={"entries": [{"printing_id": "me01-001", "count": 4}, {"printing_id": "sve-001", "count": 56}]},
    )

    assert response.json()["violations"] == []


async def test_normal_labelled_special_energy_is_subject_to_the_4_copy_rule(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    response = await client.post(
        "/decks/validate",
        json={
            "entries": [
                {"printing_id": "me01-001", "count": 4},
                {"printing_id": "me02-124", "count": 5},
                {"printing_id": "sve-002", "count": 51},
            ]
        },
    )

    violations = response.json()["violations"]
    assert [v["code"] for v in violations] == ["four_copy_limit"]
    assert violations[0]["cards"] == ["me02-124"]


async def test_a_textless_energy_with_a_non_basic_name_is_subject_to_the_4_copy_rule(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    response = await client.post(
        "/decks/validate",
        json={
            "entries": [
                {"printing_id": "me01-001", "count": 4},
                {"printing_id": "me01-130", "count": 5},
                {"printing_id": "sve-002", "count": 51},
            ]
        },
    )

    assert [v["code"] for v in response.json()["violations"]] == ["four_copy_limit"]


async def test_a_ptcgl_basic_energy_line_imports_against_the_real_basic_energy(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    response = await client.post("/decks/import", json={"text": "8 Basic Fire Energy"})

    assert response.status_code == 200
    assert [entry["printing_id"] for entry in response.json()["entries"]] == ["mee-002"]


async def test_basic_energy_never_appears_in_search(client: AsyncClient, db_session: AsyncSession) -> None:
    await _ingest(db_session)

    response = await client.post("/search", json={"filters": {"format": None, "category": "Energy"}})

    names = {result["name"] for result in response.json()["results"]}
    assert names == {"Ignition Energy", "Reversal Energy", "Mystery Energy"}


async def test_the_special_energy_pill_finds_normal_labelled_special_energies(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    response = await client.post(
        "/search", json={"filters": {"format": None, "category": "Energy", "energy_type": "Special"}}
    )

    names = {result["name"] for result in response.json()["results"]}
    assert names == {"Ignition Energy", "Reversal Energy", "Mystery Energy"}


async def test_basic_energy_is_never_submitted_for_enrichment(db_session: AsyncSession) -> None:
    await _ingest(db_session)

    await submit_enrichment_batch(db_session, StubEnrichmentClient({}))

    submitted = set(await db_session.scalars(select(CardEnrichment.dedupe_key)))
    assert submitted == {
        _dedupe_key(_POKEMON),
        _dedupe_key(_TEXTLESS_SPECIAL),
        _dedupe_key(load_printing("me02-124")),
        _dedupe_key(load_printing("sv04-266")),
    }
