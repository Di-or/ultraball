from collections.abc import Collection, Set
from dataclasses import dataclass
from datetime import date

from app.catalog.energy import EnergyType, derive_energy_type
from app.catalog.identity import build_card_identity
from app.catalog.legality import derive_is_standard_legal
from app.catalog.set_codes import derive_set_code
from app.catalog.sub_category import derive_sub_category


@dataclass(frozen=True)
class CardProjection:
    """A typed `cards` row projected from one raw TCGdex printing."""

    id: str
    set_id: str
    set_code: str
    set_name: str
    local_id: str
    name: str
    category: str
    hp: int | None
    types: list[str]
    stage: str | None
    evolve_from: str | None
    retreat: int | None
    regulation_mark: str | None
    rarity: str | None
    trainer_type: str | None
    energy_type: EnergyType | None  # derived from card text, never TCGdex's `energyType`
    attacks: list[dict]
    abilities: list[dict]
    attack_costs: list[int]
    sub_category: list[str]
    image: str | None
    dedupe_key: str
    canonical_card_text: str
    is_standard_legal: bool
    release_date: date


def project_card(
    raw: dict,
    *,
    set_id: str,
    release_date: date,
    standard_legal_marks: Collection[str],
    banned_dedupe_keys: Set[str],
    official_abbreviation: str | None = None,
    set_name: str = "",
) -> CardProjection:
    attacks = raw.get("attacks") or []
    identity = build_card_identity(raw)
    energy_type = derive_energy_type(category=raw["category"], name=raw["name"], effect=raw.get("effect"))
    regulation_mark = _normalize_regulation_mark(raw.get("regulationMark"))
    rarity = _missing_if_none_string(raw.get("rarity"))

    return CardProjection(
        id=raw["id"],
        set_id=set_id,
        set_code=derive_set_code(set_id, official_abbreviation),
        set_name=set_name,
        local_id=str(raw.get("localId", "")),
        name=raw["name"],
        category=raw["category"],
        hp=raw.get("hp"),
        types=list(raw.get("types") or []),
        stage=_normalize_stage(raw.get("stage")),
        evolve_from=raw.get("evolveFrom"),
        retreat=raw.get("retreat"),
        regulation_mark=regulation_mark,
        rarity=rarity,
        trainer_type=raw.get("trainerType"),
        energy_type=energy_type,
        attacks=attacks,
        abilities=raw.get("abilities") or [],
        attack_costs=[len(attack.get("cost") or []) for attack in attacks],
        sub_category=derive_sub_category(name=raw["name"], rarity=rarity),
        image=raw.get("image"),
        dedupe_key=identity.dedupe_key,
        canonical_card_text=identity.canonical_card_text,
        is_standard_legal=derive_is_standard_legal(
            regulation_mark=regulation_mark,
            category=raw["category"],
            energy_type=energy_type,
            dedupe_key=identity.dedupe_key,
            standard_legal_marks=standard_legal_marks,
            banned_dedupe_keys=banned_dedupe_keys,
        ),
        release_date=release_date,
    )


# TCGdex writes stages without the space; the app's filters, parse schema and frontend use it.
_STAGE_NAMES = {"Stage1": "Stage 1", "Stage2": "Stage 2"}


def _normalize_stage(stage: str | None) -> str | None:
    return _STAGE_NAMES.get(stage, stage) if stage is not None else None


def _normalize_regulation_mark(mark: str | None) -> str | None:
    """Uppercased (TCGdex has lowercase marks, e.g. `mep-051`'s `"j"`); `"None"` read as missing."""
    mark = _missing_if_none_string(mark)
    return mark.upper() if mark is not None else None


def _missing_if_none_string(value: str | None) -> str | None:
    """TCGdex writes some missing regulation marks and rarities as the literal string `"None"`."""
    return None if value == "None" else value
