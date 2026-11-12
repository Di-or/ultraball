import re
from dataclasses import dataclass

_WHITESPACE = re.compile(r"\s+")

# TCGdex writes an energy type three ways in effect text: `[R]`, `{R}` and `Fire`.
_SYMBOL_TYPE_NAMES = {
    "R": "Fire",
    "W": "Water",
    "G": "Grass",
    "L": "Lightning",
    "P": "Psychic",
    "F": "Fighting",
    "D": "Darkness",
    "M": "Metal",
    "N": "Dragon",
    "Y": "Fairy",
    "C": "Colorless",
}
_SYMBOL_LETTER = f"[{''.join(_SYMBOL_TYPE_NAMES)}]"
_ENERGY_SYMBOL = re.compile(rf"\[({_SYMBOL_LETTER})\]|\{{({_SYMBOL_LETTER})\}}")
# Adjacent symbols (`{C}{C}{C}`) are one run, written as separate words.
_ENERGY_SYMBOL_RUN = re.compile(rf"(?:{_ENERGY_SYMBOL.pattern})+")


@dataclass(frozen=True)
class CardIdentity:
    """The dedupe_key and canonical_card_text derived from one shared assembly.

    Both are built from the same rules-text serialization so identity and enrichment
    input can never drift apart (see CONTEXT.md: dedupe_key, canonical card text).
    """

    dedupe_key: str
    canonical_card_text: str
    has_rules_text: bool


def build_card_identity(raw: dict) -> CardIdentity:
    name = str(raw["name"])
    rules_text = _assemble_rules_text(raw)
    canonical_card_text = f"{name}\n{rules_text}".strip()
    dedupe_key = _normalize(f"{name} {rules_text}")
    return CardIdentity(
        dedupe_key=dedupe_key, canonical_card_text=canonical_card_text, has_rules_text=bool(rules_text)
    )


def _assemble_rules_text(raw: dict) -> str:
    """Effect-bearing text only: attacks, abilities, and Trainer/Energy effect.

    Deliberately excludes flavor text and the filter-gate scalars (hp, types,
    retreat) — those live as their own indexed columns, not in identity text.
    """
    parts: list[str] = []

    for ability in raw.get("abilities") or []:
        parts.append(f"Ability: {ability.get('name', '')} - {spell_out_energy_symbols(ability.get('effect', ''))}")

    for attack in raw.get("attacks") or []:
        cost = "/".join(attack.get("cost") or [])
        damage = attack.get("damage")
        damage_part = f" {damage}" if damage is not None else ""
        effect_text = spell_out_energy_symbols(attack.get("effect", ""))
        parts.append(f"Attack: {attack.get('name', '')} [{cost}]{damage_part} - {effect_text}")

    effect = raw.get("effect")
    if effect:
        parts.append(spell_out_energy_symbols(effect))

    return "\n".join(part.strip() for part in parts if part.strip())


def spell_out_energy_symbols(effect_text: object) -> str:
    """Write `[R]` / `{R}` energy symbols as type names, so reprints that differ only
    in notation share one dedupe_key and the tagging model reads a plain type name."""
    return _ENERGY_SYMBOL_RUN.sub(_type_names_for_run, str(effect_text))


def _type_names_for_run(run: re.Match[str]) -> str:
    return " ".join(
        _SYMBOL_TYPE_NAMES[bracketed or braced] for bracketed, braced in _ENERGY_SYMBOL.findall(run.group(0))
    )


def _normalize(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().lower()
