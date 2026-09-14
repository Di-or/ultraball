from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_card as _card


async def test_returns_one_representative_printing_per_basic_energy_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            _card(
                id="base1-98",
                dedupe_key="fire-energy",
                name="Fire Energy",
                category="Energy",
                energy_type="Basic",
                types=["Fire"],
                stage=None,
                release_date=date(1999, 1, 9),
            ),
            _card(
                id="base4-98",
                dedupe_key="fire-energy",
                name="Fire Energy",
                category="Energy",
                energy_type="Basic",
                types=["Fire"],
                stage=None,
                release_date=date(2020, 1, 1),
            ),
            _card(
                id="base1-99",
                dedupe_key="water-energy",
                name="Water Energy",
                category="Energy",
                energy_type="Basic",
                types=["Water"],
                stage=None,
                release_date=date(1999, 1, 9),
            ),
            _card(
                id="obf-1",
                dedupe_key="reversal-energy",
                name="Reversal Energy",
                category="Energy",
                energy_type="Special",
                stage=None,
                release_date=date(2023, 1, 1),
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/energy/basics")

    assert response.status_code == 200
    body = response.json()
    printing_ids = [item["printing_id"] for item in body["palette"]]
    assert "base4-98" in printing_ids
    assert "base1-98" not in printing_ids  # older reprint, superseded
    assert "base1-99" in printing_ids
    assert "obf-1" not in printing_ids  # Special Energy, not basic
