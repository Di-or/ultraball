from app.catalog.legality import derive_is_standard_legal
from app.catalog.legality_config import STANDARD_LEGAL_MARKS


def test_the_current_rotation_is_h_i_j() -> None:
    assert STANDARD_LEGAL_MARKS == frozenset({"H", "I", "J"})


def test_under_the_current_rotation_a_j_card_is_legal_and_a_g_card_is_not() -> None:
    def legal(mark: str) -> bool:
        return derive_is_standard_legal(
            regulation_mark=mark,
            category="Pokemon",
            energy_type=None,
            dedupe_key="some-card",
            standard_legal_marks=STANDARD_LEGAL_MARKS,
            banned_dedupe_keys=frozenset(),
        )

    assert legal("J") is True
    assert legal("G") is False


def test_under_the_current_rotation_basic_energy_with_a_rotated_mark_is_still_legal() -> None:
    assert derive_is_standard_legal(
        regulation_mark="G",
        category="Energy",
        energy_type="Basic",
        dedupe_key="basic-fire-energy",
        standard_legal_marks=STANDARD_LEGAL_MARKS,
        banned_dedupe_keys=frozenset(),
    ) is True


def test_card_within_the_allowed_mark_range_is_legal() -> None:
    assert derive_is_standard_legal(
        regulation_mark="G",
        category="Pokemon",
        energy_type=None,
        dedupe_key="some-card",
        standard_legal_marks={"F", "G", "H"},
        banned_dedupe_keys=frozenset(),
    ) is True


def test_card_with_a_rotated_out_mark_is_not_legal() -> None:
    assert derive_is_standard_legal(
        regulation_mark="D",
        category="Pokemon",
        energy_type=None,
        dedupe_key="some-card",
        standard_legal_marks={"F", "G", "H"},
        banned_dedupe_keys=frozenset(),
    ) is False


def test_card_with_no_regulation_mark_is_not_legal() -> None:
    assert derive_is_standard_legal(
        regulation_mark=None,
        category="Pokemon",
        energy_type=None,
        dedupe_key="some-card",
        standard_legal_marks={"F", "G", "H"},
        banned_dedupe_keys=frozenset(),
    ) is False


def test_banned_card_is_not_legal_despite_an_otherwise_legal_mark() -> None:
    assert derive_is_standard_legal(
        regulation_mark="G",
        category="Pokemon",
        energy_type=None,
        dedupe_key="banned-card",
        standard_legal_marks={"F", "G", "H"},
        banned_dedupe_keys=frozenset({"banned-card"}),
    ) is False


def test_basic_energy_is_always_legal_regardless_of_mark() -> None:
    assert derive_is_standard_legal(
        regulation_mark="D",
        category="Energy",
        energy_type="Basic",
        dedupe_key="basic-fire-energy",
        standard_legal_marks={"F", "G", "H"},
        banned_dedupe_keys=frozenset(),
    ) is True


def test_basic_energy_is_legal_even_with_no_regulation_mark() -> None:
    assert derive_is_standard_legal(
        regulation_mark=None,
        category="Energy",
        energy_type="Basic",
        dedupe_key="basic-fire-energy",
        standard_legal_marks={"F", "G", "H"},
        banned_dedupe_keys=frozenset(),
    ) is True


def test_special_energy_is_not_exempt_from_the_mark_check() -> None:
    assert derive_is_standard_legal(
        regulation_mark="D",
        category="Energy",
        energy_type="Special",
        dedupe_key="some-special-energy",
        standard_legal_marks={"F", "G", "H"},
        banned_dedupe_keys=frozenset(),
    ) is False


def test_ban_list_overrides_the_basic_energy_exception() -> None:
    assert derive_is_standard_legal(
        regulation_mark="H",
        category="Energy",
        energy_type="Basic",
        dedupe_key="banned-basic-energy",
        standard_legal_marks={"F", "G", "H"},
        banned_dedupe_keys=frozenset({"banned-basic-energy"}),
    ) is False


def test_rotation_is_a_config_edit_that_flips_a_card_without_touching_the_card() -> None:
    args = dict(
        regulation_mark="F",
        category="Pokemon",
        energy_type=None,
        dedupe_key="some-card",
        banned_dedupe_keys=frozenset(),
    )

    assert derive_is_standard_legal(**args, standard_legal_marks={"F", "G", "H"}) is True
    assert derive_is_standard_legal(**args, standard_legal_marks={"G", "H", "I"}) is False
