from collections.abc import Collection, Set
from dataclasses import dataclass
from datetime import date

from app.catalog.identity import build_card_identity
from app.catalog.legality import derive_is_standard_legal


@dataclass(frozen=True)
class CardProjection:
    """A typed `cards` row projected from one raw TCGdex printing."""

    id: str
    set_id: str
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
    energy_type: str | None
    attacks: list[dict]
    abilities: list[dict]
    attack_costs: list[int]
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
) -> CardProjection:
    attacks = raw.get("attacks") or []
    identity = build_card_identity(raw)

    return CardProjection(
        id=raw["id"],
        set_id=set_id,
        local_id=str(raw.get("localId", "")),
        name=raw["name"],
        category=raw["category"],
        hp=raw.get("hp"),
        types=list(raw.get("types") or []),
        stage=raw.get("stage"),
        evolve_from=raw.get("evolveFrom"),
        retreat=raw.get("retreat"),
        regulation_mark=raw.get("regulationMark"),
        rarity=raw.get("rarity"),
        trainer_type=raw.get("trainerType"),
        energy_type=raw.get("energyType"),
        attacks=attacks,
        abilities=raw.get("abilities") or [],
        attack_costs=[len(attack.get("cost") or []) for attack in attacks],
        dedupe_key=identity.dedupe_key,
        canonical_card_text=identity.canonical_card_text,
        is_standard_legal=derive_is_standard_legal(
            regulation_mark=raw.get("regulationMark"),
            category=raw["category"],
            energy_type=raw.get("energyType"),
            dedupe_key=identity.dedupe_key,
            standard_legal_marks=standard_legal_marks,
            banned_dedupe_keys=banned_dedupe_keys,
        ),
        release_date=release_date,
    )
