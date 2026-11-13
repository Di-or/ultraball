"""`/energy/basics` is always the eight `MEE 1`-`8` printings (issue #147; CONTEXT.md: Basic-Energy tray)."""

from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.ingest import run_ingest
from tests.factories import make_card as _card
from tests.stubs import StubCatalogClient
from tests.tcgdex_fixtures import fixture_snapshot

_MEE_1_TO_8 = [f"mee-00{n}" for n in range(1, 9)]


async def test_returns_exactly_mee_1_to_8_in_tray_order(client: AsyncClient, db_session: AsyncSession) -> None:
    # `mee` also holds MEE 12 ("Basic Lightning Energy"), and `sve` older Basic Energy.
    catalog_client = StubCatalogClient({set_id: fixture_snapshot(set_id) for set_id in ("sve", "mee")})
    for set_id in ("sve", "mee"):
        await run_ingest(db_session, catalog_client, set_id)

    response = await client.get("/energy/basics")

    assert response.status_code == 200
    palette = response.json()["palette"]
    assert [item["printing_id"] for item in palette] == _MEE_1_TO_8
    assert [item["name"] for item in palette] == [
        "Grass Energy",
        "Fire Energy",
        "Water Energy",
        "Lightning Energy",
        "Psychic Energy",
        "Fighting Energy",
        "Darkness Energy",
        "Metal Energy",
    ]


async def test_a_newer_basic_energy_printing_does_not_displace_the_mee_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    basic = dict(category="Energy", energy_type="Basic", stage=None, set_id="mee", set_code="MEE")
    db_session.add_all(
        [
            _card(id="mee-002", dedupe_key="fire-energy", name="Fire Energy", local_id="002", **basic),
            _card(id="mee-010", dedupe_key="fire-energy", name="Basic Fire Energy", local_id="010", **basic),
            _card(
                id="zzz-002",
                dedupe_key="fire-energy",
                name="Fire Energy",
                category="Energy",
                energy_type="Basic",
                stage=None,
                set_id="zzz",
                set_code="ZZZ",
                local_id="002",
                release_date=date(2030, 1, 1),
            ),
            _card(
                id="obf-1",
                dedupe_key="reversal-energy",
                name="Reversal Energy",
                category="Energy",
                energy_type="Special",
                stage=None,
                set_id="mee",
                set_code="MEE",
                local_id="001",
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/energy/basics")

    assert [item["printing_id"] for item in response.json()["palette"]] == ["mee-002"]
