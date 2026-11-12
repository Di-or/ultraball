from app.catalog.set_codes import SET_CODE_OVERRIDES, derive_local_id, derive_set_code


def test_derives_from_official_abbreviation() -> None:
    assert derive_set_code("sv3pt5", "MEW") == "MEW"


def test_uppercases_a_lowercase_official_abbreviation() -> None:
    assert derive_set_code("obf", "obf") == "OBF"


def test_falls_back_to_the_set_id_when_no_official_abbreviation_is_known() -> None:
    assert derive_set_code("swsh1", None) == "SWSH1"


def test_an_override_wins_over_the_official_abbreviation() -> None:
    SET_CODE_OVERRIDES["some-set"] = "OVR"
    try:
        assert derive_set_code("some-set", "SOMESET") == "OVR"
    finally:
        del SET_CODE_OVERRIDES["some-set"]


def test_a_classic_collection_printing_takes_its_printed_cc_number() -> None:
    # TCGdex numbers the 30th Celebration Classic Collection 001-030 in its own order;
    # PTCGL writes the printed `CC` number: `Shining Celebi 30C CC6`, `Solgaleo-GX 30C CC23`.
    assert derive_local_id("30th-c-024", "024") == "CC6"
    assert derive_local_id("30th-c-017", "017") == "CC23"


def test_the_two_legend_halves_are_cc16_top_and_cc17_bottom() -> None:
    assert derive_local_id("30th-c-019", "019") == "CC16"
    assert derive_local_id("30th-c-020", "020") == "CC17"


def test_every_classic_collection_printing_has_its_own_cc_number() -> None:
    numbers = [derive_local_id(f"30th-c-{n:03}", f"{n:03}") for n in range(1, 31)]

    assert sorted(numbers) == sorted(f"CC{n}" for n in range(1, 31))


def test_any_other_printing_keeps_tcgdex_s_local_id() -> None:
    assert derive_local_id("30th-017", "017") == "017"
