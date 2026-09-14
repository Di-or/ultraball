from app.catalog.set_codes import SET_CODE_OVERRIDES, derive_set_code


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
