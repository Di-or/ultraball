"""Card art in the API: ready-to-use image URLs, an image fallback for a representative
printing with none, and art from outside TCGdex through a catalog override.

TCGdex leaves whole promo sets without images (research/pre-tagging-pipeline-check.md,
finding 12), and those printings often carry the newest regulation mark, so they are often
the representative printing.
"""

from dataclasses import replace

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.ingest import run_ingest
from app.catalog.overrides import CatalogOverrides
from tests.stubs import StubCatalogClient
from tests.tcgdex_fixtures import fixture_snapshot, load_printing

# The four real Paradise Resort printings: one card entity.
_G_WITH_IMAGE = "svp-045"
_H_WITH_IMAGE = "svp-150"
_I_NO_IMAGE = "svp-224"
_J_NO_IMAGE = "mep-092"  # newest mark, so the representative

_SVP_045_ART = "https://assets.tcgdex.net/en/sv/svp/045/high.webp"
_SVP_150_ART = "https://assets.tcgdex.net/en/sv/svp/150/high.webp"


async def _ingest_paradise_resort(db_session: AsyncSession, overrides: CatalogOverrides | None = None) -> None:
    catalog_client = StubCatalogClient(
        {
            "svp": fixture_snapshot("svp", [_G_WITH_IMAGE, _H_WITH_IMAGE, _I_NO_IMAGE]),
            "mep": fixture_snapshot("mep", [_J_NO_IMAGE]),
        }
    )
    for set_id in ("svp", "mep"):
        await run_ingest(db_session, catalog_client, set_id, overrides=overrides or {})


async def _detail(client: AsyncClient, printing_id: str) -> dict:
    response = await client.get(f"/cards/{printing_id}")
    assert response.status_code == 200
    return response.json()


async def test_a_representative_with_no_image_shows_the_best_ranked_printing_with_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _ingest_paradise_resort(db_session)

    detail = await _detail(client, _G_WITH_IMAGE)

    assert detail["printing_id"] == _J_NO_IMAGE
    assert detail["regulation_mark"] == "J"
    assert detail["is_standard_legal"] is True
    assert detail["image"] == _SVP_150_ART  # H outranks G; I and J have no art


async def test_each_printing_in_the_list_keeps_its_own_art(client: AsyncClient, db_session: AsyncSession) -> None:
    await _ingest_paradise_resort(db_session)

    detail = await _detail(client, _J_NO_IMAGE)

    assert [(p["printing_id"], p["image"]) for p in detail["printings"]] == [
        (_J_NO_IMAGE, None),
        (_I_NO_IMAGE, None),
        (_H_WITH_IMAGE, _SVP_150_ART),
        (_G_WITH_IMAGE, _SVP_045_ART),
    ]


async def test_an_override_can_give_a_printing_art_from_outside_tcgdex(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    art = "https://images.example.com/paradise-resort/mep-092.png"
    await _ingest_paradise_resort(db_session, overrides={_J_NO_IMAGE: {"image": art}})

    detail = await _detail(client, _H_WITH_IMAGE)

    assert detail["printing_id"] == _J_NO_IMAGE
    assert detail["image"] == art  # the representative's own art, not the fallback
    assert (detail["printings"][0]["printing_id"], detail["printings"][0]["image"]) == (_J_NO_IMAGE, art)


async def test_an_override_can_point_at_a_complete_tcgdex_image(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # A full file URL on TCGdex's own host is used as is, not treated as a base URL.
    art = "https://assets.tcgdex.net/en/sv/svp/150/high.png"
    await _ingest_paradise_resort(db_session, overrides={_J_NO_IMAGE: {"image": art}})

    assert (await _detail(client, _J_NO_IMAGE))["image"] == art


async def test_the_energy_tray_gets_small_tcgdex_art(client: AsyncClient, db_session: AsyncSession) -> None:
    fire = {**load_printing("mee-002"), "image": "https://assets.tcgdex.net/en/me/mee/002"}
    catalog_client = StubCatalogClient({"mee": replace(fixture_snapshot("mee", []), cards=[fire])})
    await run_ingest(db_session, catalog_client, "mee", overrides={})

    response = await client.get("/energy/basics")

    assert [entry["image"] for entry in response.json()["palette"]] == [
        "https://assets.tcgdex.net/en/me/mee/002/low.webp"
    ]
