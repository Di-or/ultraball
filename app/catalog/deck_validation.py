from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.catalog.models import Card

# Full Standard ruleset (CONTEXT.md: Standard-legal; docs/archive/mvp-spec.md §12.3).
_REQUIRED_DECK_SIZE = 60
_MAX_COPIES_PER_NAME = 4
_MAX_ACE_SPEC = 1


@dataclass(frozen=True)
class DeckLine:
    """One resolved deck entry: a printing plus how many copies (CONTEXT.md: Printing)."""

    card: Card
    count: int


@dataclass(frozen=True)
class Violation:
    code: str
    message: str
    cards: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Counts:
    pokemon: int
    trainer: int
    energy: int
    total: int


@dataclass(frozen=True)
class LegalityReport:
    legal: bool
    counts: Counts
    violations: list[Violation]


def _is_basic_energy(card: Card) -> bool:
    return card.category == "Energy" and card.energy_type == "Basic"


def _is_ace_spec(card: Card) -> bool:
    return "ace-spec" in card.sub_category


def validate_deck(
    lines: Sequence[DeckLine], *, unresolved_printing_ids: Sequence[str] = ()
) -> LegalityReport:
    """Allow-and-flag Standard legality: every violation is reported, nothing blocks (CONTEXT.md:
    Standard-legal; docs/archive/mvp-spec.md §12.3 — the builder accepts any corpus card).

    `unresolved_printing_ids` are entries whose `printing_id` didn't resolve to a catalog row;
    they can't be typed or legality-checked, but still count toward deck size since the user put
    that many cards in the deck, so they're surfaced as their own violation.
    """
    violations: list[Violation] = []

    declared_total = sum(line.count for line in lines) + len(unresolved_printing_ids)
    if declared_total != _REQUIRED_DECK_SIZE:
        violations.append(
            Violation(
                code="deck_size",
                message=f"Deck has {declared_total} cards; must be exactly {_REQUIRED_DECK_SIZE}.",
            )
        )

    if unresolved_printing_ids:
        violations.append(
            Violation(
                code="unknown_printing",
                message="Some printing ids are not in the catalog.",
                cards=list(unresolved_printing_ids),
            )
        )

    # 4-copy rule keys on the printed Name, coarser than dedupe_key (CONTEXT.md: Name (4-copy key)).
    by_name: dict[str, list[DeckLine]] = defaultdict(list)
    for line in lines:
        if not _is_basic_energy(line.card):
            by_name[line.card.name].append(line)

    for name, group in by_name.items():
        copies = sum(line.count for line in group)
        if copies > _MAX_COPIES_PER_NAME:
            violations.append(
                Violation(
                    code="four_copy_limit",
                    message=f'"{name}" has {copies} copies; at most {_MAX_COPIES_PER_NAME} allowed.',
                    cards=[line.card.id for line in group],
                )
            )

    illegal = [line for line in lines if not line.card.is_standard_legal]
    if illegal:
        violations.append(
            Violation(
                code="not_standard_legal",
                message="Some cards are not Standard-legal.",
                cards=[line.card.id for line in illegal],
            )
        )

    has_basic_pokemon = any(
        line.card.category == "Pokemon" and line.card.stage == "Basic" and line.count > 0 for line in lines
    )
    if not has_basic_pokemon:
        violations.append(Violation(code="no_basic_pokemon", message="Deck has no Basic Pokémon."))

    ace_spec_lines = [line for line in lines if _is_ace_spec(line.card)]
    ace_spec_count = sum(line.count for line in ace_spec_lines)
    if ace_spec_count > _MAX_ACE_SPEC:
        violations.append(
            Violation(
                code="ace_spec_limit",
                message=f"Deck has {ace_spec_count} ACE SPEC cards; at most {_MAX_ACE_SPEC} allowed.",
                cards=[line.card.id for line in ace_spec_lines],
            )
        )

    counts = Counts(
        pokemon=sum(line.count for line in lines if line.card.category == "Pokemon"),
        trainer=sum(line.count for line in lines if line.card.category == "Trainer"),
        energy=sum(line.count for line in lines if line.card.category == "Energy"),
        total=declared_total,
    )

    return LegalityReport(legal=not violations, counts=counts, violations=violations)
