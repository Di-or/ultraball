# PTCGL identifies a printing by `{set_code} {local_id}` (e.g. "OBF 10"). The set code is
# auto-derived from TCGdex's `set.abbreviation.official`; this map covers the handful of
# sets where PTCGL's code diverges from that official abbreviation (issue #28).
SET_CODE_OVERRIDES: dict[str, str] = {}


def derive_set_code(set_id: str, official_abbreviation: str | None) -> str:
    """The PTCGL-facing set code for one set (CONTEXT.md: catalog layer; issue #28)."""
    if set_id in SET_CODE_OVERRIDES:
        return SET_CODE_OVERRIDES[set_id]
    if official_abbreviation:
        return official_abbreviation.upper()
    return set_id.upper()
