import re
from datetime import date

from app.catalog.models import Card
from app.enrichment import status
from app.enrichment.models import CardEnrichment
from app.enrichment.taxonomy import PROMPT_VERSION, TAXONOMY_VERSION


def make_card(**overrides: object) -> Card:
    """A minimally-valid `Card` row with sensible defaults, for tests that don't ingest."""
    base = dict(
        id=overrides.pop("id", "swsh1-1"),
        set_id="swsh1",
        set_code="SWSH1",
        set_name="Sword & Shield",
        local_id="1",
        name="Charizard",
        category="Pokemon",
        hp=170,
        types=["Fire"],
        stage="Stage 2",
        evolve_from="Charmeleon",
        retreat=3,
        regulation_mark="H",
        rarity="Rare Holo",
        trainer_type=None,
        energy_type=None,
        attacks=[],
        abilities=[],
        attack_costs=[4],
        sub_category=[],
        image="https://assets.tcgdex.net/en/swsh/swsh1/1",
        dedupe_key=overrides.pop("dedupe_key", "charizard-1"),
        canonical_card_text="Charizard",
        is_standard_legal=True,
        release_date=date(2023, 1, 1),
    )
    base.update(overrides)
    return Card(**base)


def make_raw_pokemon(**overrides: object) -> dict[str, object]:
    """A minimally-valid raw TCGdex Basic Pokémon printing, for tests that run it through ingest."""
    printing_id = str(overrides.pop("id", "sv1-1"))
    base: dict[str, object] = dict(
        id=printing_id,
        localId=printing_id.split("-")[1],
        name="Sprigatito",
        category="Pokemon",
        hp=60,
        types=["Grass"],
        stage="Basic",
        regulationMark="H",
        attacks=[{"name": "Tackle", "cost": ["Colorless"], "damage": 10, "effect": ""}],
        abilities=[],
    )
    base.update(overrides)
    return base


def make_tcgdex_pokemon(**overrides: object) -> dict[str, object]:
    """A raw printing in TCGdex's real Pokémon shape (compare `tests/fixtures/tcgdex/`).

    Unlike `make_raw_pokemon`: `localId` is the zero-padded suffix of `id`, the stage is written
    TCGdex's way (`Stage1` / `Stage2`), and there's no `abilities` key unless one is given.
    Any field can be overridden; `None` leaves the key out, as TCGdex does.
    """
    printing_id = str(overrides.pop("id", "me01-001"))
    base: dict[str, object] = dict(
        _tcgdex_printing_base(printing_id),
        category="Pokemon",
        name="Bulbasaur",
        rarity="Common",
        hp=70,
        types=["Grass"],
        stage="Basic",
        attacks=[{"cost": ["Grass"], "name": "Vine Whip", "damage": 20, "effect": ""}],
        retreat=1,
        regulationMark="I",
    )
    return _apply_overrides(base, overrides)


def make_tcgdex_trainer(**overrides: object) -> dict[str, object]:
    """A raw printing in TCGdex's real Trainer shape. `None` leaves a field out."""
    printing_id = str(overrides.pop("id", "me01-113"))
    base: dict[str, object] = dict(
        _tcgdex_printing_base(printing_id),
        category="Trainer",
        name="Potion",
        rarity="Common",
        trainerType="Item",
        effect="Heal 30 damage from 1 of your Pokémon.",
        regulationMark="I",
    )
    return _apply_overrides(base, overrides)


def make_tcgdex_basic_energy(energy: str = "Fire", **overrides: object) -> dict[str, object]:
    """A raw Basic Energy printing as TCGdex sends it: `energyType: "Normal"`, no effect text,
    and (like every `sve` printing) no image or regulation mark.

    `energy` names the card (`"Water"` → `Water Energy`). `None` leaves a field out.
    """
    printing_id = str(overrides.pop("id", "sve-002"))
    base: dict[str, object] = dict(
        _tcgdex_printing_base(printing_id),
        image=None,
        category="Energy",
        name=f"{energy} Energy",
        rarity="Common",
        energyType="Normal",
    )
    return _apply_overrides(base, overrides)


def make_tcgdex_special_energy(**overrides: object) -> dict[str, object]:
    """A raw Special Energy printing as TCGdex sends ME-era ones: also `energyType: "Normal"`,
    told apart from Basic Energy only by its effect text. `None` leaves a field out."""
    printing_id = str(overrides.pop("id", "me02-124"))
    base: dict[str, object] = dict(
        _tcgdex_printing_base(printing_id),
        category="Energy",
        name="Ignition Energy",
        rarity="Uncommon",
        effect=(
            "If this card is attached to 1 of your Pokémon, discard it at the end of your turn.\n\n"
            "As long as this card is attached to a Pokémon, it provides {C} Energy.\n\n"
            "If this card is attached to an Evolution Pokémon, it provides {C}{C}{C} Energy instead."
        ),
        energyType="Normal",
        regulationMark="I",
    )
    return _apply_overrides(base, overrides)


def _tcgdex_printing_base(printing_id: str) -> dict[str, object]:
    """The fields every TCGdex printing carries, derived from its id (`<set id>-<local id>`)."""
    set_id, local_id = printing_id.rsplit("-", 1)
    return dict(
        id=printing_id,
        localId=local_id,
        set={"id": set_id, "name": set_id},
        image=f"https://assets.tcgdex.net/en/{_tcgdex_series(set_id)}/{set_id}/{local_id}",
    )


def _tcgdex_series(set_id: str) -> str:
    """The series segment of a TCGdex image URL: `svp` and `sve` are `sv`, `mep` and `30th` are `me`."""
    if set_id.startswith("sv"):
        return "sv"
    if set_id.startswith(("me", "30th")):
        return "me"
    return re.sub(r"[^a-z].*", "", set_id) or set_id


def _apply_overrides(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = {**base, **overrides}
    return {key: value for key, value in merged.items() if value is not None}


def make_enrichment(**overrides: object) -> CardEnrichment:
    """A minimally-valid `CardEnrichment` row, for tests exercising tag-match retrieval."""
    base = dict(
        dedupe_key=overrides.pop("dedupe_key", "charizard-1"),
        normalized_description=None,
        tags=[],
        suggested_new_tag=None,
        rationale=None,
        vector=None,
        taxonomy_version=TAXONOMY_VERSION,
        prompt_version=PROMPT_VERSION,
        status=status.COMPLETED,
        batch_id=None,
    )
    base.update(overrides)
    return CardEnrichment(**base)
