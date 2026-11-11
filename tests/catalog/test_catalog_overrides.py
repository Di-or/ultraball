"""Catalog overrides: hand-kept fixes to one printing's TCGdex data (issue #112).

An override is applied to the raw JSON before projection, so it reaches every column and the
`dedupe_key`, while the raw snapshot keeps what TCGdex sent. Each ingest reports overrides
whose field TCGdex now supplies, so a redundant or disagreeing entry can be reviewed.
"""

from dataclasses import replace
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.ingest import run_ingest
from app.catalog.models import Card, RawCard
from app.catalog.overrides import OverrideCheck
from app.clients.catalog_client import SetSnapshot
from tests.factories import make_tcgdex_trainer
from tests.stubs import StubCatalogClient
from tests.tcgdex_fixtures import fixture_snapshot, load_printing

_ULTRA_BALL_TEXT = (
    "You can use this card only if you discard 2 other cards from your hand.\n\n"
    "Search your deck for a Pokémon, reveal it, and put it into your hand. Then, shuffle your deck."
)

# Another Ultra Ball printing, with the English text TCGdex has for it.
_SV01_ULTRA_BALL = make_tcgdex_trainer(
    id="sv01-196", name="Ultra Ball", rarity="Uncommon", regulationMark="G", effect=_ULTRA_BALL_TEXT
)
_SV01_RELEASE = date(2023, 3, 31)

# `mfb-33` stores its regulation mark as the string "None".
_NONE_MARK_ID = "mfb-33"


def _thirtieth(ultra_ball: dict | None = None) -> SetSnapshot:
    snapshot = fixture_snapshot("30th", ["30th-128"])
    return replace(snapshot, cards=[ultra_ball]) if ultra_ball is not None else snapshot


async def _ingest_ultra_balls(
    db_session: AsyncSession, overrides: dict | None = None, *, thirtieth_ultra_ball: dict | None = None
) -> list[OverrideCheck]:
    catalog_client = StubCatalogClient(
        {"30th": _thirtieth(thirtieth_ultra_ball), "sv01": SetSnapshot("sv01", _SV01_RELEASE, [_SV01_ULTRA_BALL])}
    )
    await run_ingest(db_session, catalog_client, "sv01")
    if overrides is None:
        return await run_ingest(db_session, catalog_client, "30th")
    return await run_ingest(db_session, catalog_client, "30th", overrides=overrides)


async def _card(db_session: AsyncSession, printing_id: str) -> Card:
    card = await db_session.get(Card, printing_id)
    assert card is not None
    await db_session.refresh(card)
    return card


async def test_an_override_fills_in_a_missing_field_in_every_derived_column(db_session: AsyncSession) -> None:
    await _ingest_ultra_balls(db_session, {"30th-128": {"effect": _ULTRA_BALL_TEXT}})

    thirtieth = await _card(db_session, "30th-128")
    sv01 = await _card(db_session, "sv01-196")
    assert thirtieth.dedupe_key == sv01.dedupe_key
    assert thirtieth.canonical_card_text == sv01.canonical_card_text
    assert not thirtieth.is_textless


async def test_the_raw_snapshot_keeps_tcgdex_values(db_session: AsyncSession) -> None:
    await _ingest_ultra_balls(db_session, {"30th-128": {"effect": _ULTRA_BALL_TEXT}})

    raw = await db_session.get(RawCard, "30th-128")
    assert raw is not None
    assert raw.raw == load_printing("30th-128")


async def test_an_override_wins_over_a_value_tcgdex_supplies(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient({"mfb": fixture_snapshot("mfb", [_NONE_MARK_ID])})

    await run_ingest(db_session, catalog_client, "mfb", overrides={_NONE_MARK_ID: {"regulationMark": "h"}})

    card = await _card(db_session, _NONE_MARK_ID)
    assert card.regulation_mark == "H"
    raw = await db_session.get(RawCard, _NONE_MARK_ID)
    assert raw is not None
    assert raw.raw["regulationMark"] == "None"


async def test_without_an_override_the_printing_keeps_tcgdex_data(db_session: AsyncSession) -> None:
    await _ingest_ultra_balls(db_session, {})

    assert (await _card(db_session, "30th-128")).is_textless


async def test_the_report_is_empty_while_tcgdex_lacks_the_overridden_field(db_session: AsyncSession) -> None:
    report = await _ingest_ultra_balls(db_session, {"30th-128": {"effect": _ULTRA_BALL_TEXT}})

    assert report == []


async def test_the_report_marks_an_override_tcgdex_now_matches_as_same(db_session: AsyncSession) -> None:
    filled_in = {**load_printing("30th-128"), "effect": _ULTRA_BALL_TEXT}

    report = await _ingest_ultra_balls(
        db_session, {"30th-128": {"effect": _ULTRA_BALL_TEXT}}, thirtieth_ultra_ball=filled_in
    )

    assert report == [
        OverrideCheck(
            printing_id="30th-128",
            field="effect",
            status="same",
            override_value=_ULTRA_BALL_TEXT,
            tcgdex_value=_ULTRA_BALL_TEXT,
        )
    ]


async def test_the_report_marks_an_override_tcgdex_disagrees_with_as_differs(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient({"mfb": fixture_snapshot("mfb", [_NONE_MARK_ID])})

    report = await run_ingest(db_session, catalog_client, "mfb", overrides={_NONE_MARK_ID: {"regulationMark": "H"}})

    assert report == [
        OverrideCheck(
            printing_id=_NONE_MARK_ID, field="regulationMark", status="differs", override_value="H", tcgdex_value="None"
        )
    ]


async def test_an_override_for_a_printing_in_another_set_is_ignored(db_session: AsyncSession) -> None:
    report = await _ingest_ultra_balls(db_session, {"zz-1": {"effect": "Draw a card."}})

    assert report == []
    assert (await _card(db_session, "30th-128")).is_textless


async def test_the_seeded_overrides_give_30th_ultra_ball_the_ultra_ball_entity(db_session: AsyncSession) -> None:
    report = await _ingest_ultra_balls(db_session)

    thirtieth = await _card(db_session, "30th-128")
    sv01 = await _card(db_session, "sv01-196")
    assert thirtieth.dedupe_key == sv01.dedupe_key
    assert report == []
