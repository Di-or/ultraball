from collections.abc import Collection, Set

from app.catalog.energy import EnergyType, is_basic_energy


def derive_is_standard_legal(
    *,
    regulation_mark: str | None,
    category: str,
    energy_type: EnergyType | None,
    dedupe_key: str,
    standard_legal_marks: Collection[str],
    banned_dedupe_keys: Set[str],
) -> bool:
    """Rules-accurate Standard legality, derived — never read from TCGdex's `legal.standard`.

    The ban list overrides every other rule, including the Basic Energy exception —
    a ban targets a specific card regardless of what would otherwise make it legal.
    Basic Energy that isn't banned is always legal, regardless of regulation mark.
    Everything else is legal iff its regulation mark is in the current rotation
    window. See CONTEXT.md: Standard-legal, Basic Energy exception, Ban list.

    `energy_type` is the derived classification from `derive_energy_type`, not TCGdex's field.
    """
    if dedupe_key in banned_dedupe_keys:
        return False

    if is_basic_energy(category=category, energy_type=energy_type):
        return True

    if regulation_mark is None:
        return False

    return regulation_mark in standard_legal_marks
