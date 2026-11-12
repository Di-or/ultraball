# PTCGL identifies a printing by `{set_code} {local_id}` (e.g. "OBF 10"). The set code is
# auto-derived from TCGdex's `set.abbreviation.official`; this map covers the handful of
# sets where PTCGL's code diverges from that official abbreviation (issue #28).
SET_CODE_OVERRIDES: dict[str, str] = {
    # TCGdex abbreviates the SV Black Star Promos `SVP`; PTCGL writes `PR-SV 187` (issue #123).
    # The Mega promos are `MEP` in both.
    "svp": "PR-SV",
}


# PTCGL numbers the 30th Celebration Classic Collection by its printed `CC1`-`CC30`
# (`Shining Celebi 30C CC6`); TCGdex numbers it `001`-`030` in a different order (issue #123).
# Printing id -> PTCGL number. Order checked against Limitless (CC6, CC16, CC17, CC23, CC24
# read directly) and three set lists that agree on every slot. The Darkrai & Cresselia LEGEND
# is two cards: TCGdex's `019` has no attacks (the top half, CC16), `020` has them (CC17).
LOCAL_ID_OVERRIDES: dict[str, str] = {
    "30th-c-014": "CC1",  # Pikachu
    "30th-c-001": "CC2",  # Charizard
    "30th-c-005": "CC3",  # Misty
    "30th-c-015": "CC4",  # Erika's Jigglypuff
    "30th-c-007": "CC5",  # Sneasel
    "30th-c-024": "CC6",  # Shining Celebi
    "30th-c-029": "CC7",  # Lugia
    "30th-c-002": "CC8",  # Delcatty
    "30th-c-006": "CC9",  # Dark Tyranitar
    "30th-c-025": "CC10",  # Scizor ex
    "30th-c-003": "CC11",  # Metagross
    "30th-c-022": "CC12",  # Palkia
    "30th-c-010": "CC13",  # Uxie
    "30th-c-011": "CC14",  # Crobat G
    "30th-c-018": "CC15",  # Gengar
    "30th-c-019": "CC16",  # Darkrai & Cresselia LEGEND (top)
    "30th-c-020": "CC17",  # Darkrai & Cresselia LEGEND (bottom)
    "30th-c-021": "CC18",  # N
    "30th-c-016": "CC19",  # Rayquaza EX
    "30th-c-004": "CC20",  # Genesect EX
    "30th-c-023": "CC21",  # M Gardevoir EX
    "30th-c-009": "CC22",  # Greninja BREAK
    "30th-c-017": "CC23",  # Solgaleo GX
    "30th-c-013": "CC24",  # Buzzwole GX
    "30th-c-008": "CC25",  # Pikachu & Zekrom GX
    "30th-c-028": "CC26",  # Zacian V
    "30th-c-012": "CC27",  # Raikou
    "30th-c-026": "CC28",  # Mew VMAX
    "30th-c-027": "CC29",  # Arceus VSTAR
    "30th-c-030": "CC30",  # Magikarp
}


def derive_local_id(printing_id: str, tcgdex_local_id: str) -> str:
    """The PTCGL-facing card number for one printing: TCGdex's `localId`, unless PTCGL prints
    another (issue #123)."""
    return LOCAL_ID_OVERRIDES.get(printing_id, tcgdex_local_id)


def derive_set_code(set_id: str, official_abbreviation: str | None) -> str:
    """The PTCGL-facing set code for one set (CONTEXT.md: catalog layer; issue #28)."""
    if set_id in SET_CODE_OVERRIDES:
        return SET_CODE_OVERRIDES[set_id]
    if official_abbreviation:
        return official_abbreviation.upper()
    return set_id.upper()
