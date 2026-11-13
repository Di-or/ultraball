"""Printings with no English rules text get no card entity (issue #113).

TCGdex publishes new sets partly filled in. A non-Energy printing with no effect, attacks or
abilities would get a `dedupe_key` built from its name alone, never matching the real card's, and
be tagged from the model's memory. Such a printing is stored, but kept out of enrichment and
search until a later ingest brings its text (and with it, a real `dedupe_key`).
"""

from dataclasses import replace
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.identity import build_card_identity
from app.catalog.ingest import run_ingest
from app.catalog.models import Card, RawCard
from app.clients.catalog_client import SetSnapshot
from app.clients.parse_client import ParseClient, ParseResult
from app.enrichment.models import CardEnrichment
from app.enrichment.pipeline import submit_enrichment_batch
from tests.factories import make_enrichment, make_tcgdex_pokemon
from tests.stubs import StubCatalogClient, StubEnrichmentClient, StubParseClient
from tests.tcgdex_fixtures import fixture_snapshot, load_printing

_ULTRA_BALL_TEXT = (
    "You can use this card only if you discard 2 other cards from your hand.\n\n"
    "Search your deck for a Pokémon, reveal it, and put it into your hand. Then, shuffle your deck."
)

# The real `30th-128` Ultra Ball: TCGdex still has no English text for it. Ingested without
# the catalog overrides, which would fill that text in.
_TEXTLESS_TRAINER_ID = "30th-128"

# A Pokémon from a half-filled set: a name, hp and stage, but no attacks or abilities yet.
_TEXTLESS_POKEMON = make_tcgdex_pokemon(id="me06-001", name="Oddish", attacks=None)
_ME06_RELEASE = date(2026, 11, 6)

# A filled-in printing ingested alongside, so search and enrichment have something to return.
_POKEMON = make_tcgdex_pokemon(id="me01-001")

# Basic Energy has no rules text either, and stays in the tray.
_FIRE_ENERGY_ID = "mee-002"


def _ultra_ball_with_text() -> dict:
    return {**load_printing(_TEXTLESS_TRAINER_ID), "effect": _ULTRA_BALL_TEXT}


async def _ingest(db_session: AsyncSession, *, ultra_ball: dict | None = None, oddish: dict | None = None) -> None:
    thirtieth = fixture_snapshot("30th", [_TEXTLESS_TRAINER_ID])
    catalog_client = StubCatalogClient(
        {
            "30th": replace(thirtieth, cards=[ultra_ball or load_printing(_TEXTLESS_TRAINER_ID)]),
            "me06": SetSnapshot("me06", _ME06_RELEASE, [oddish or _TEXTLESS_POKEMON]),
            "me01": SetSnapshot("me01", date(2025, 9, 26), [_POKEMON]),
            "mee": fixture_snapshot("mee", [_FIRE_ENERGY_ID]),
        }
    )
    for set_id in ("30th", "me06", "me01", "mee"):
        await run_ingest(db_session, catalog_client, set_id, overrides={})


async def _submitted_dedupe_keys(db_session: AsyncSession) -> set[str]:
    await submit_enrichment_batch(db_session, StubEnrichmentClient({}))
    return set(await db_session.scalars(select(CardEnrichment.dedupe_key)))


async def _search_names(client: AsyncClient, filters: dict | None = None) -> set[str]:
    response = await client.post("/search", json={"filters": {"format": None, **(filters or {})}})
    assert response.status_code == 200
    return {result["name"] for result in response.json()["results"]}


def _dedupe_key(raw: dict) -> str:
    return build_card_identity(raw).dedupe_key


async def test_a_textless_printing_is_still_stored(db_session: AsyncSession) -> None:
    await _ingest(db_session)

    for printing_id in (_TEXTLESS_TRAINER_ID, "me06-001"):
        assert await db_session.get(RawCard, printing_id) is not None
        assert await db_session.get(Card, printing_id) is not None


async def test_a_textless_printing_is_never_submitted_for_enrichment(db_session: AsyncSession) -> None:
    await _ingest(db_session)

    assert await _submitted_dedupe_keys(db_session) == {_dedupe_key(_POKEMON)}


async def test_a_textless_printing_never_appears_in_search(client: AsyncClient, db_session: AsyncSession) -> None:
    await _ingest(db_session)

    assert await _search_names(client) == {"Bulbasaur"}
    assert await _search_names(client, {"category": "Trainer"}) == set()


@pytest.fixture
def parse_client() -> ParseClient:
    """Every query parses to the `search` tag, so search routes to tag-match ranking."""
    return StubParseClient(ParseResult(filters={"format": None}, concept="search the deck", tags=["search"]))


async def test_a_textless_printing_tagged_before_this_rule_stays_out_of_tag_match(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)
    # A tagging answer stored for the name-only key, e.g. by a run before textless printings were excluded.
    db_session.add(make_enrichment(dedupe_key=_dedupe_key(load_printing(_TEXTLESS_TRAINER_ID)), tags=["search"]))
    db_session.add(make_enrichment(dedupe_key=_dedupe_key(_POKEMON), tags=["search"]))
    await db_session.commit()

    response = await client.post("/search", json={"query": "cards that search the deck"})

    assert response.status_code == 200
    assert {result["name"] for result in response.json()["results"]} == {"Bulbasaur"}


async def test_basic_energy_is_exempt(client: AsyncClient, db_session: AsyncSession) -> None:
    await _ingest(db_session)

    response = await client.get("/energy/basics")

    assert [item["printing_id"] for item in response.json()["palette"]] == [_FIRE_ENERGY_ID]


async def test_re_ingesting_a_printing_once_it_has_text_makes_it_a_normal_entity(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)
    await submit_enrichment_batch(db_session, StubEnrichmentClient({}))

    filled_oddish = {**_TEXTLESS_POKEMON, "attacks": [{"cost": ["Grass"], "name": "Ram", "damage": 10}]}
    await _ingest(db_session, ultra_ball=_ultra_ball_with_text(), oddish=filled_oddish)

    assert await _submitted_dedupe_keys(db_session) == {
        _dedupe_key(_POKEMON),
        _dedupe_key(_ultra_ball_with_text()),
        _dedupe_key(filled_oddish),
    }
    assert await _search_names(client) == {"Bulbasaur", "Oddish", "Ultra Ball"}
