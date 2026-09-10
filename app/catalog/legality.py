from collections.abc import Collection, Set


def derive_is_standard_legal(
    *,
    regulation_mark: str | None,
    category: str,
    energy_type: str | None,
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
    """
    if dedupe_key in banned_dedupe_keys:
        return False

    if category == "Energy" and energy_type == "Basic":
        return True

    if regulation_mark is None:
        return False

    return regulation_mark in standard_legal_marks
