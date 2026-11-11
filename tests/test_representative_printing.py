"""The representative printing: newest regulation mark, then newest release date, then has an
image, then printing id (CONTEXT.md: Representative printing; issue #124).

Promo sets share one series-wide release date, and one ingest run gives every printing the same
`ingested_at`, so ordering by release date alone left the representative to ingest order
(research/pre-tagging-pipeline-check.md, finding 8).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.ingest import run_ingest
from tests.stubs import StubCatalogClient
from tests.tcgdex_fixtures import fixture_snapshot, load_printing

# Real Paradise Resort promos, both in `svp` (one release date): G is not Standard, H is.
_PARADISE_RESORT_G = "svp-045"
_PARADISE_RESORT_H = "svp-150"

# Real Pikachu promos, one entity: G with an image, H without (research finding 13: their HP differs).
_PIKACHU_G_WITH_IMAGE = "svp-101"
_PIKACHU_H_NO_IMAGE = "svp-190"

_BOTH_ORDERS = pytest.mark.parametrize("reverse", [False, True], ids=["in-order", "reversed"])


async def _ingest_svp(db_session: AsyncSession, printings: list[dict], *, reverse: bool) -> None:
    snapshot = fixture_snapshot("svp", [])
    snapshot.cards.extend(reversed(printings) if reverse else printings)
    await run_ingest(db_session, StubCatalogClient({"svp": snapshot}), "svp", overrides={})


async def _search_printing_ids(client: AsyncClient, name: str, *, format: str | None) -> list[str]:
    response = await client.post("/search", json={"query": None, "filters": {"format": format}})
    assert response.status_code == 200
    return [result["printing_id"] for result in response.json()["results"] if result["name"] == name]


async def _detail(client: AsyncClient, printing_id: str) -> dict:
    response = await client.get(f"/cards/{printing_id}")
    assert response.status_code == 200
    return response.json()


@_BOTH_ORDERS
async def test_a_promo_tie_resolves_to_the_legal_printing_whatever_the_ingest_order(
    client: AsyncClient, db_session: AsyncSession, reverse: bool
) -> None:
    pair = [load_printing(_PARADISE_RESORT_G), load_printing(_PARADISE_RESORT_H)]
    await _ingest_svp(db_session, pair, reverse=reverse)

    assert await _search_printing_ids(client, "Paradise Resort", format="standard") == [_PARADISE_RESORT_H]
    assert await _search_printing_ids(client, "Paradise Resort", format=None) == [_PARADISE_RESORT_H]
    for asked_for in (_PARADISE_RESORT_G, _PARADISE_RESORT_H):
        detail = await _detail(client, asked_for)
        assert detail["printing_id"] == _PARADISE_RESORT_H
        assert detail["is_standard_legal"] is True
        assert [p["printing_id"] for p in detail["printings"]] == [_PARADISE_RESORT_H, _PARADISE_RESORT_G]


@_BOTH_ORDERS
async def test_the_newer_regulation_mark_outranks_having_an_image(
    client: AsyncClient, db_session: AsyncSession, reverse: bool
) -> None:
    pair = [load_printing(_PIKACHU_G_WITH_IMAGE), load_printing(_PIKACHU_H_NO_IMAGE)]
    await _ingest_svp(db_session, pair, reverse=reverse)

    assert await _search_printing_ids(client, "Pikachu", format=None) == [_PIKACHU_H_NO_IMAGE]
    assert (await _detail(client, _PIKACHU_G_WITH_IMAGE))["printing_id"] == _PIKACHU_H_NO_IMAGE


@_BOTH_ORDERS
async def test_on_the_same_mark_and_date_a_printing_with_an_image_wins(
    client: AsyncClient, db_session: AsyncSession, reverse: bool
) -> None:
    # The G Pikachu re-marked H: now only the image tells the two apart.
    with_image = {**load_printing(_PIKACHU_G_WITH_IMAGE), "regulationMark": "H"}
    await _ingest_svp(db_session, [with_image, load_printing(_PIKACHU_H_NO_IMAGE)], reverse=reverse)

    assert await _search_printing_ids(client, "Pikachu", format=None) == [_PIKACHU_G_WITH_IMAGE]
    detail = await _detail(client, _PIKACHU_H_NO_IMAGE)
    assert [p["printing_id"] for p in detail["printings"]] == [_PIKACHU_G_WITH_IMAGE, _PIKACHU_H_NO_IMAGE]


@_BOTH_ORDERS
async def test_a_full_tie_breaks_on_printing_id(
    client: AsyncClient, db_session: AsyncSession, reverse: bool
) -> None:
    # Same mark, same date, both with an image: only the printing id is left.
    both = [load_printing(_PARADISE_RESORT_H), {**load_printing(_PARADISE_RESORT_G), "regulationMark": "H"}]
    await _ingest_svp(db_session, both, reverse=reverse)

    assert await _search_printing_ids(client, "Paradise Resort", format=None) == [_PARADISE_RESORT_G]
    assert (await _detail(client, _PARADISE_RESORT_H))["printing_id"] == _PARADISE_RESORT_G
