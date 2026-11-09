"""Refresh the real TCGdex JSON test fixtures in `tests/fixtures/tcgdex/`.

Run by hand: `uv run python -m scripts.fetch_tcgdex_fixtures`. Not part of the app or the test
run: tests only read the committed files (`tests/tcgdex_fixtures.py`).

Each printing in `FIXTURE_PRINTINGS` is saved to `cards/<printing id>.json`, and the set it
belongs to to `sets/<set id>.json`. Requests bypass TCGdex's CDN cache (`Cache-Control:
no-cache` plus a cache-busting query parameter), because a plain request can return a copy
that is weeks old (research/pre-tagging-pipeline-check.md, 2026-11-08 corrections).

The JSON is stored as TCGdex sends it, except that `pricing` (on the card and on each entry of
`variants_detailed`) is dropped: it changes daily, so it would turn every refresh into a noisy
diff, and the app never reads it.
"""

import asyncio
import json
import time
from pathlib import Path

import httpx

_API = "https://api.tcgdex.net/v2/en"
_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "tcgdex"
_ATTEMPTS = 4

# Why each printing is here (issue #108). See research/pre-tagging-pipeline-check.md.
FIXTURE_PRINTINGS = {
    "sve-002": 'Basic Energy (Fire): `energyType: "Normal"`, no effect, no image or mark',
    "me02-124": 'ME-era Special Energy (Ignition Energy) that TCGdex labels `"Normal"`',
    "sv04-266": 'Reversal Energy: a pre-ME Special Energy labelled `"Normal"`',
    "mep-023": "Mega Charizard X ex promo: `Stage2`, zero-padded localId, no image, one half "
    "of the energy-symbol drift pair",
    "me02-013": "Mega Charizard X ex: the other half of the drift pair, with an image",
    "svp-101": "Pikachu promo with an image (mark G); svp shares one series-wide release date",
    "svp-190": "Pikachu promo without an image (mark H, different HP), same svp release date",
    "30th-128": "Ultra Ball: a non-Energy printing with no English rules text",
    "mep-051": 'Oshawott: lowercase regulation mark `"j"`',
    "mfb-33": 'Potion: regulation mark and rarity are the string `"None"`',
}


async def _get_json(client: httpx.AsyncClient, path: str) -> dict:
    # Uncached requests reach TCGdex's origin, which answers 503 under load: go one at a
    # time and retry a few times.
    for attempt in range(_ATTEMPTS):
        response = await client.get(
            f"{_API}/{path}",
            params={"cb": str(time.time_ns())},
            headers={"Cache-Control": "no-cache"},
        )
        if response.status_code < 500 or attempt == _ATTEMPTS - 1:
            response.raise_for_status()
            return response.json()
        await asyncio.sleep(2**attempt)
    raise AssertionError("unreachable")


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        cards = [await _get_json(client, f"cards/{printing_id}") for printing_id in FIXTURE_PRINTINGS]
        set_ids = sorted({card["set"]["id"] for card in cards})
        sets = [await _get_json(client, f"sets/{set_id}") for set_id in set_ids]

    for card in cards:
        card.pop("pricing", None)
        for variant in card.get("variants_detailed", []):
            variant.pop("pricing", None)
        _write(_FIXTURES_DIR / "cards" / f"{card['id']}.json", card)
    for set_json in sets:
        _write(_FIXTURES_DIR / "sets" / f"{set_json['id']}.json", set_json)
    print(f"Wrote {len(cards)} printings and {len(sets)} sets to {_FIXTURES_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
