from pydantic import BaseModel

from app.catalog.models import Card
from app.search.models import Matched


class Printing(BaseModel):
    """One printing of the card entity (CONTEXT.md: Printing) — for the reprint list."""

    model_config = {"from_attributes": True}

    printing_id: str
    set_id: str
    regulation_mark: str | None
    rarity: str | None
    image: str | None
    is_standard_legal: bool

    @classmethod
    def from_card(cls, card: Card) -> "Printing":
        return cls(
            printing_id=card.id,
            set_id=card.set_id,
            regulation_mark=card.regulation_mark,
            rarity=card.rarity,
            image=card.image,
            is_standard_legal=card.is_standard_legal,
        )


class CardDetail(BaseModel):
    """The card-detail view (docs/archive/mvp-spec.md §12.4) for the representative printing.

    Deliberately excludes `normalized_description` — internal-only, would
    contradict the printed text shown beside it (CONTEXT.md: Normalized
    mechanical description).
    """

    entity_id: str
    printing_id: str
    name: str
    category: str
    hp: int | None
    types: list[str]
    stage: str | None
    evolve_from: str | None
    retreat: int | None
    regulation_mark: str | None
    rarity: str | None
    set_id: str
    sub_category: list[str]
    trainer_type: str | None
    energy_type: str | None
    attacks: list[dict]
    abilities: list[dict]
    attack_costs: list[int]
    image: str | None
    is_standard_legal: bool
    tags: list[str]
    printings: list[Printing]
    matched: Matched | None = None

    @classmethod
    def from_card(
        cls,
        card: Card,
        *,
        tags: list[str],
        printings: list[Card],
        matched: Matched | None = None,
    ) -> "CardDetail":
        return cls(
            entity_id=card.dedupe_key,
            printing_id=card.id,
            name=card.name,
            category=card.category,
            hp=card.hp,
            types=card.types,
            stage=card.stage,
            evolve_from=card.evolve_from,
            retreat=card.retreat,
            regulation_mark=card.regulation_mark,
            rarity=card.rarity,
            set_id=card.set_id,
            sub_category=card.sub_category,
            trainer_type=card.trainer_type,
            energy_type=card.energy_type,
            attacks=card.attacks,
            abilities=card.abilities,
            attack_costs=card.attack_costs,
            image=card.image,
            is_standard_legal=card.is_standard_legal,
            tags=tags,
            printings=[Printing.from_card(printing) for printing in printings],
            matched=matched,
        )
