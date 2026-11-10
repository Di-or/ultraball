import re
from typing import Literal

# The nine types printed as Basic Energy. Dragon and Colorless never had a Basic Energy card.
_BASIC_ENERGY_TYPES = ("Grass", "Fire", "Water", "Lightning", "Psychic", "Fighting", "Darkness", "Metal", "Fairy")

_BASIC_ENERGY_NAME = re.compile(rf"(?:basic )?(?:{'|'.join(_BASIC_ENERGY_TYPES)}) energy", re.IGNORECASE)

EnergyType = Literal["Basic", "Special"]


def derive_energy_type(raw: dict) -> EnergyType | None:
    """Whether a raw TCGdex printing is Basic or Special Energy; `None` if it isn't Energy at all.

    Basic Energy is an Energy card with no effect text **and** a basic name ("Basic <Type> Energy"
    or "<Type> Energy"). Both must hold, so a Special Energy whose text is missing fails safe as
    an ordinary (Special) card. TCGdex's `energyType` is never consulted: it labels Basic Energy
    and many Special Energies alike `"Normal"`. See CONTEXT.md: Basic Energy exception.
    """
    if raw.get("category") != "Energy":
        return None

    has_effect_text = bool((raw.get("effect") or "").strip())
    name = " ".join(str(raw.get("name") or "").split())
    if not has_effect_text and _BASIC_ENERGY_NAME.fullmatch(name):
        return "Basic"

    return "Special"
