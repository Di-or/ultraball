"""A real PTCGL export imports through `POST /decks/import` (issue #123).

The catalog is ingested from real TCGdex JSON, which zero-pads card numbers (`localId: "086"`)
while PTCGL writes them bare (`SVI 86`). `30th` and `30th-c` both derive the set code `30C`, and
both have a card `001` in TCGdex, though PTCGL numbers the Classic Collection `CC1`-`CC30`.
Basic Energy lines come as `Basic {R} Energy SVE 2` or a bare `Basic Fire Energy`.
"""

from pathlib import Path

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.ingest import run_ingest
from tests.stubs import StubCatalogClient
from tests.tcgdex_fixtures import fixture_snapshot

_SETS = ("sv01", "sv02", "sv03", "sv04", "sve", "me02", "30th", "30th-c")

# As PTCGL's "Export" button writes it, section headers and total included.
_REAL_EXPORT = """\
Pokémon: 4
2 Charizard ex OBF 125
1 Mega Charizard X ex PFL 13
1 Charizard 30C CC2

Trainer: 9
4 Iono PAL 185
4 Ultra Ball SVI 196
1 Ultra Ball 30C 128

Energy: 11
2 Ignition Energy PFL 124
1 Reversal Energy PAR 266
8 Basic {R} Energy SVE 2

Total Cards: 24
"""


async def _ingest(db_session: AsyncSession) -> None:
    catalog_client = StubCatalogClient({set_id: fixture_snapshot(set_id) for set_id in _SETS})
    for set_id in _SETS:
        await run_ingest(db_session, catalog_client, set_id)


async def _import(client: AsyncClient, text: str) -> list[tuple[str, int]]:
    response = await client.post("/decks/import", json={"text": text})
    assert response.status_code == 200, response.json()
    return [(entry["printing_id"], entry["count"]) for entry in response.json()["entries"]]


async def test_every_line_of_a_real_export_resolves_to_its_zero_padded_printing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    entries = await _import(client, _REAL_EXPORT)

    assert sorted(entries) == sorted(
        [
            ("sv03-125", 2),
            ("me02-013", 1),
            ("30th-c-001", 1),
            ("sv02-185", 4),
            ("sv01-196", 4),
            ("30th-128", 1),
            ("me02-124", 2),
            ("sv04-266", 1),
            ("sve-002", 8),
        ]
    )


async def test_a_set_code_shared_by_two_sets_finds_each_set_s_cards(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    entries = await _import(client, "1 Exeggcute 30C 1\n1 Charizard 30C CC2")

    assert entries == [("30th-001", 1), ("30th-c-001", 1)]


async def test_classic_collection_lines_from_a_real_ptcgl_export_resolve_by_cc_number(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    # Copied from PTCGL. TCGdex numbers these `024` and `017`.
    entries = await _import(client, "1 Shining Celebi 30C CC6\n1 Solgaleo-GX 30C CC23")

    assert entries == [("30th-c-024", 1), ("30th-c-017", 1)]


async def test_a_set_code_shared_by_two_sets_finds_a_number_only_one_of_them_has(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    assert await _import(client, "1 Ultra Ball 30C 128") == [("30th-128", 1)]


async def test_a_zero_padded_number_in_the_export_also_resolves(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    assert await _import(client, "4 Ultra Ball SVI 0196") == [("sv01-196", 4)]


async def test_bare_basic_energy_lines_resolve_to_the_basic_energy_palette(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    for line in ("8 Basic Fire Energy", "8 Basic {R} Energy", "8 Fire Energy"):
        assert await _import(client, line) == [("sve-002", 8)], line


async def test_a_basic_energy_line_with_an_unknown_set_tail_falls_back_to_the_palette(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    # Older PTCGL exports wrote the set code for Basic Energy as "Energy".
    assert await _import(client, "8 Basic {R} Energy Energy 2") == [("sve-002", 8)]


async def test_a_basic_energy_line_resolves_to_the_palette_whatever_its_set_tail_names(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    # `SVI 196` is Ultra Ball: the Basic Energy name wins over the tail.
    assert await _import(client, "8 Basic {R} Energy SVI 196") == [("sve-002", 8)]


async def test_a_line_whose_set_tail_names_no_printing_fails_even_if_its_name_is_energy_like(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    response = await client.post("/decks/import", json={"text": "2 Ignition Energy PFL 999"})

    assert response.status_code == 422


async def test_a_name_that_matches_no_printing_with_that_number_still_fails(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    response = await client.post("/decks/import", json={"text": "4 Iono SVI 999"})

    assert response.status_code == 422
    assert response.json()["detail"]["lines"] == ["4 Iono SVI 999"]


# A decklist exported by Limitless's deckbuilder that PTCGL imported cleanly: SV promos as
# `PR-SV`, Basic Energy by name with its set code, from both the SV and Mega Energy sets.
_PTCGL_COMPATIBLE_EXPORT = (Path(__file__).parent / "fixtures" / "ptcgl" / "limitless_export.txt").read_text(
    encoding="utf-8"
)
_EXPORT_SETS = ("svp", "sve", "mee", "mep", "me05", "me02.5", "sv06.5", "sv06", "sv05", "me04")


async def test_a_ptcgl_compatible_export_imports_every_printing_exactly(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    catalog_client = StubCatalogClient({set_id: fixture_snapshot(set_id) for set_id in _EXPORT_SETS})
    for set_id in _EXPORT_SETS:
        await run_ingest(db_session, catalog_client, set_id)

    entries = await _import(client, _PTCGL_COMPATIBLE_EXPORT)

    assert entries == [
        ("mep-007", 2),
        ("mep-020", 2),
        ("svp-187", 2),
        ("svp-202", 1),
        ("mep-010", 1),
        ("mep-034", 1),
        ("me05-080", 1),
        ("me02.5-181", 1),
        ("sv06.5-055", 1),
        ("sv06.5-054", 1),
        ("sv06.5-060", 1),
        ("sv06-145", 1),
        ("sve-001", 1),
        ("sve-002", 2),
        ("sve-003", 2),
        ("mee-004", 1),
        ("mee-005", 1),
        ("mee-006", 1),
        ("mee-007", 1),
        ("mee-008", 1),
        ("mee-012", 1),  # a second Lightning printing: the exact one, not the palette's
        ("sv05-161", 1),
        ("me04-084", 1),
    ]


async def test_a_30th_celebration_line_from_a_real_ptcgl_export_resolves(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest(db_session)

    # Copied from PTCGL. TCGdex also numbers Solgaleo GX `017` (`30th-c-017`), but PTCGL calls it
    # `CC23`, so only Lapras is `30C 17`.
    assert await _import(client, "1 Lapras 30C 17") == [("30th-017", 1)]
