import re
from typing import Literal

from sqlalchemy import ColumnElement, or_
from sqlalchemy.orm import QueryableAttribute

from app.catalog.identity import spell_out_energy_symbols

# The eight Basic Energy types in play (CONTEXT.md: Basic-Energy tray). Dragon and Colorless never had a
# Basic Energy card, and Fairy is out of rotation, so a Fairy Energy is treated as an ordinary card.
_BASIC_ENERGY_TYPES = ("Grass", "Fire", "Water", "Lightning", "Psychic", "Fighting", "Darkness", "Metal")

_BASIC_ENERGY_NAME = re.compile(rf"(?:basic )?(?:{'|'.join(_BASIC_ENERGY_TYPES)}) energy", re.IGNORECASE)

# How a decklist names Basic Energy: also `Basic {R} Energy`, or the bare type (`Fire`).
_DECKLIST_BASIC_ENERGY_NAME = re.compile(
    rf"(?:basic )?(?P<type>{'|'.join(_BASIC_ENERGY_TYPES)})(?: energy)?", re.IGNORECASE
)

EnergyType = Literal["Basic", "Special"]


def derive_energy_type(*, category: str, name: str, effect: str | None) -> EnergyType | None:
    """Whether a printing is Basic or Special Energy; `None` if it isn't Energy at all.

    Basic Energy is an Energy card with no effect text **and** a basic name ("Basic <Type> Energy"
    or "<Type> Energy"). Both must hold, so a Special Energy whose text is missing fails safe as
    an ordinary (Special) card. TCGdex's `energyType` is never consulted: it labels Basic Energy
    and many Special Energies alike `"Normal"`. See CONTEXT.md: Basic Energy exception.
    """
    if category != "Energy":
        return None

    has_effect_text = bool((effect or "").strip())
    if not has_effect_text and _BASIC_ENERGY_NAME.fullmatch(" ".join(name.split())):
        return "Basic"

    return "Special"


def basic_energy_type_named(name: str) -> str | None:
    """The type a decklist line's Basic Energy name names ("Fire" for `Basic {R} Energy`,
    `Basic Fire Energy`, `Fire Energy` or `Fire`), or `None` if it doesn't name Basic Energy.

    Looser than `derive_energy_type`'s name test, which reads card names rather than
    decklist lines (issue #123)."""
    match = _DECKLIST_BASIC_ENERGY_NAME.fullmatch(" ".join(spell_out_energy_symbols(name).split()))
    return match.group("type").title() if match else None


def is_basic_energy(*, category: str, energy_type: str | None) -> bool:
    """The Basic Energy test on a projected row, whose `energy_type` came from `derive_energy_type`."""
    return category == "Energy" and energy_type == "Basic"


def basic_energy_clause(
    category: QueryableAttribute[str], energy_type: QueryableAttribute[str | None]
) -> ColumnElement[bool]:
    """`is_basic_energy` as a SQL predicate over a `cards` table (or an alias of it)."""
    return (category == "Energy") & (energy_type == "Basic")


def not_basic_energy_clause(
    category: QueryableAttribute[str], energy_type: QueryableAttribute[str | None]
) -> ColumnElement[bool]:
    """Everything outside Basic Energy, NULL-safe: one half of `corpus_clause`."""
    return or_(category != "Energy", energy_type.is_distinct_from("Basic"))
