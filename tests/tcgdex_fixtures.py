"""Real TCGdex JSON, committed under `tests/fixtures/tcgdex/` (issue #108).

Each printing was picked for a quirk of TCGdex's real data that hand-written fixtures missed;
`scripts/fetch_tcgdex_fixtures.py` lists why each one is here and refreshes them.
"""

import json
from datetime import date
from pathlib import Path

from app.clients.catalog_client import SetSnapshot

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "tcgdex"

FIXTURE_PRINTING_IDS: tuple[str, ...] = tuple(
    sorted(path.stem for path in (_FIXTURES_DIR / "cards").glob("*.json"))
)


def load_printing(printing_id: str) -> dict:
    """One printing's card JSON as TCGdex sends it. A fresh copy each call, safe to modify."""
    return _read(_FIXTURES_DIR / "cards" / f"{printing_id}.json")


def load_set(set_id: str) -> dict:
    """One set's JSON as TCGdex sends it, including its brief card list."""
    return _read(_FIXTURES_DIR / "sets" / f"{set_id}.json")


def fixture_snapshot(set_id: str, printing_ids: list[str] | None = None) -> SetSnapshot:
    """A `SetSnapshot` built from the real set JSON, holding the named printings.

    By default it holds every committed printing from the set.
    """
    set_json = load_set(set_id)
    if printing_ids is None:
        printing_ids = [pid for pid in FIXTURE_PRINTING_IDS if load_printing(pid)["set"]["id"] == set_id]
    return SetSnapshot(
        set_id=set_id,
        release_date=date.fromisoformat(set_json["releaseDate"]),
        cards=[load_printing(pid) for pid in printing_ids],
        official_abbreviation=(set_json.get("abbreviation") or {}).get("official"),
        name=set_json["name"],
    )


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
