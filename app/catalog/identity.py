import re
from dataclasses import dataclass

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class CardIdentity:
    """The dedupe_key and canonical_card_text derived from one shared assembly.

    Both are built from the same rules-text serialization so identity and enrichment
    input can never drift apart (see CONTEXT.md: dedupe_key, canonical card text).
    """

    dedupe_key: str
    canonical_card_text: str


def build_card_identity(raw: dict) -> CardIdentity:
    name = str(raw["name"])
    rules_text = _assemble_rules_text(raw)
    canonical_card_text = f"{name}\n{rules_text}".strip()
    dedupe_key = _normalize(f"{name} {rules_text}")
    return CardIdentity(dedupe_key=dedupe_key, canonical_card_text=canonical_card_text)


def _assemble_rules_text(raw: dict) -> str:
    """Effect-bearing text only: attacks, abilities, and Trainer/Energy effect.

    Deliberately excludes flavor text and the filter-gate scalars (hp, types,
    retreat) — those live as their own indexed columns, not in identity text.
    """
    parts: list[str] = []

    for ability in raw.get("abilities") or []:
        parts.append(f"Ability: {ability.get('name', '')} - {ability.get('effect', '')}")

    for attack in raw.get("attacks") or []:
        cost = "/".join(attack.get("cost") or [])
        damage = attack.get("damage")
        damage_part = f" {damage}" if damage is not None else ""
        parts.append(f"Attack: {attack.get('name', '')} [{cost}]{damage_part} - {attack.get('effect', '')}")

    effect = raw.get("effect")
    if effect:
        parts.append(str(effect))

    return "\n".join(part.strip() for part in parts if part.strip())


def _normalize(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().lower()
