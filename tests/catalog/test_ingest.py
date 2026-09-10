from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.identity import build_card_identity
from app.catalog.ingest import run_ingest
from app.catalog.models import Card, RawCard
from app.catalog.queries import get_representative_printing
from app.clients.catalog_client import SetSnapshot
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
    "attacks": [
        {"name": "Fire Spin", "cost": ["Fire", "Fire", "Colorless", "Colorless"], "damage": 100, "effect": "Discard 2 Energy."},
    ],
    "abilities": [],
}

_CHARIZARD_REPRINT = {
    **_CHARIZARD,
    "id": "base4-4",
    "localId": "4",
    "regulationMark": "H",
    "rarity": "Rare Holo",
}

_LUGIA_BANNED = {
    "id": "sm1-1",
    "localId": "1",
    "name": "Lugia",
    "category": "Pokemon",
    "hp": 90,
    "types": ["Colorless"],
    "stage": "Basic",
    "regulationMark": "H",
    "attacks": [{"name": "Aeroblast", "cost": ["Colorless"], "damage": 30, "effect": ""}],
    "abilities": [],
}

_FIRE_ENERGY = {
    "id": "base1-98",
    "localId": "98",
    "name": "Fire Energy",
    "category": "Energy",
    "energyType": "Basic",
    "attacks": [],
    "abilities": [],
}


async def test_ingest_stores_a_raw_snapshot_per_printing(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient({"base1": SetSnapshot("base1", date(1999, 1, 9), [_CHARIZARD, _FIRE_ENERGY])})

    await run_ingest(db_session, catalog_client, "base1")

    raw = await db_session.scalar(select(RawCard).where(RawCard.id == "base1-4"))
    assert raw is not None
    assert raw.raw["name"] == "Charizard"


async def test_ingest_projects_typed_scalar_and_jsonb_columns(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient({"base1": SetSnapshot("base1", date(1999, 1, 9), [_CHARIZARD])})

    await run_ingest(db_session, catalog_client, "base1")

    card = await db_session.scalar(select(Card).where(Card.id == "base1-4"))
    assert card is not None
    assert card.hp == 120
    assert card.types == ["Fire"]
    assert card.attack_costs == [4]
    assert card.attacks[0]["name"] == "Fire Spin"


async def test_genuine_reprints_collapse_to_one_dedupe_key(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient(
        {
            "base1": SetSnapshot("base1", date(1999, 1, 9), [_CHARIZARD]),
            "base4": SetSnapshot("base4", date(2000, 8, 16), [_CHARIZARD_REPRINT]),
        }
    )

    await run_ingest(db_session, catalog_client, "base1")
    await run_ingest(db_session, catalog_client, "base4")

    count = await db_session.scalar(
        select(func.count(func.distinct(Card.dedupe_key))).where(Card.id.in_(["base1-4", "base4-4"]))
    )
    assert count == 1


async def test_representative_printing_is_the_most_recent_reprint(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient(
        {
            "base1": SetSnapshot("base1", date(1999, 1, 9), [_CHARIZARD]),
            "base4": SetSnapshot("base4", date(2000, 8, 16), [_CHARIZARD_REPRINT]),
        }
    )
    await run_ingest(db_session, catalog_client, "base1")
    await run_ingest(db_session, catalog_client, "base4")

    old_printing = await db_session.scalar(select(Card).where(Card.id == "base1-4"))
    assert old_printing is not None

    representative = await get_representative_printing(db_session, old_printing.dedupe_key)

    assert representative is not None
    assert representative.id == "base4-4"


async def test_is_standard_legal_is_derived_across_marks_ban_list_and_basic_energy(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient(
        {"base1": SetSnapshot("base1", date(1999, 1, 9), [_CHARIZARD, _LUGIA_BANNED, _FIRE_ENERGY])}
    )
    banned_dedupe_key = build_card_identity(_LUGIA_BANNED).dedupe_key

    await run_ingest(
        db_session,
        catalog_client,
        "base1",
        standard_legal_marks=frozenset({"H"}),
        banned_dedupe_keys=frozenset({banned_dedupe_key}),
    )

    charizard = await db_session.scalar(select(Card).where(Card.id == "base1-4"))
    lugia = await db_session.scalar(select(Card).where(Card.id == "sm1-1"))
    fire_energy = await db_session.scalar(select(Card).where(Card.id == "base1-98"))

    assert charizard is not None and charizard.regulation_mark == "D"
    assert charizard.is_standard_legal is False
    assert lugia is not None and lugia.is_standard_legal is False
    assert fire_energy is not None and fire_energy.is_standard_legal is True


async def test_re_ingesting_a_set_after_a_rotation_edit_flips_legality(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient({"base1": SetSnapshot("base1", date(1999, 1, 9), [_CHARIZARD])})

    await run_ingest(db_session, catalog_client, "base1", standard_legal_marks=frozenset({"D"}))
    legal_before = await db_session.scalar(select(Card).where(Card.id == "base1-4"))
    assert legal_before is not None and legal_before.is_standard_legal is True

    await run_ingest(db_session, catalog_client, "base1", standard_legal_marks=frozenset({"G", "H"}))
    db_session.expire_all()  # ingest upserts via Core, bypassing the ORM identity map
    legal_after = await db_session.scalar(select(Card).where(Card.id == "base1-4"))
    assert legal_after is not None and legal_after.is_standard_legal is False
