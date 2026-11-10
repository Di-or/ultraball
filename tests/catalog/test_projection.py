from datetime import date

import pytest

from app.catalog.projection import CardProjection, project_card
from tests.factories import make_tcgdex_basic_energy, make_tcgdex_special_energy, make_tcgdex_trainer


def _raw_pokemon(**overrides: object) -> dict:
    base = {
        "id": "swsh1-178",
        "localId": "178",
        "name": "Charizard",
        "category": "Pokemon",
        "hp": 170,
        "types": ["Fire"],
        "stage": "Stage 2",
        "evolveFrom": "Charmeleon",
        "retreat": 3,
        "regulationMark": "D",
        "rarity": "Rare Holo",
        "attacks": [
            {"name": "Fire Spin", "cost": ["Fire", "Fire", "Colorless", "Colorless"], "damage": 100, "effect": "Discard 2 Energy."},
        ],
        "abilities": [],
        "legal": {"standard": False},
    }
    base.update(overrides)
    return base


def test_projects_scalars_and_derives_attack_costs() -> None:
    card = project_card(
        _raw_pokemon(),
        set_id="swsh1",
        release_date=date(2020, 2, 7),
        standard_legal_marks=frozenset({"D"}),
        banned_dedupe_keys=frozenset(),
    )

    assert card.id == "swsh1-178"
    assert card.set_id == "swsh1"
    assert card.name == "Charizard"
    assert card.category == "Pokemon"
    assert card.hp == 170
    assert card.types == ["Fire"]
    assert card.regulation_mark == "D"
    assert card.attack_costs == [4]
    assert card.release_date == date(2020, 2, 7)


def test_derives_is_standard_legal_from_config_not_from_raw_legal_field() -> None:
    legal_by_config = project_card(
        _raw_pokemon(regulationMark="D", legal={"standard": False}),
        set_id="swsh1",
        release_date=date(2020, 2, 7),
        standard_legal_marks=frozenset({"D"}),
        banned_dedupe_keys=frozenset(),
    )

    assert legal_by_config.is_standard_legal is True


def test_attack_costs_derived_per_attack_for_multi_attack_cards() -> None:
    card = project_card(
        _raw_pokemon(
            attacks=[
                {"name": "Scratch", "cost": ["Colorless"], "damage": 10, "effect": ""},
                {"name": "Flamethrower", "cost": ["Fire", "Fire", "Colorless"], "damage": 90, "effect": ""},
            ]
        ),
        set_id="swsh1",
        release_date=date(2020, 2, 7),
        standard_legal_marks=frozenset({"D"}),
        banned_dedupe_keys=frozenset(),
    )

    assert card.attack_costs == [1, 3]


def test_basic_energy_projection_is_always_legal() -> None:
    card = project_card(
        {
            "id": "swsh1-170",
            "localId": "170",
            "name": "Fire Energy",
            "category": "Energy",
            "energyType": "Normal",  # as TCGdex labels it
            "attacks": [],
            "abilities": [],
        },
        set_id="swsh1",
        release_date=date(2020, 2, 7),
        standard_legal_marks=frozenset({"G"}),
        banned_dedupe_keys=frozenset(),
    )

    assert card.is_standard_legal is True
    assert card.attack_costs == []


def test_set_code_is_derived_from_the_official_abbreviation() -> None:
    card = project_card(
        _raw_pokemon(),
        set_id="sv3pt5",
        release_date=date(2023, 6, 2),
        standard_legal_marks=frozenset({"D"}),
        banned_dedupe_keys=frozenset(),
        official_abbreviation="MEW",
    )

    assert card.set_code == "MEW"


def test_set_code_falls_back_to_the_set_id_without_an_official_abbreviation() -> None:
    card = project_card(
        _raw_pokemon(),
        set_id="swsh1",
        release_date=date(2020, 2, 7),
        standard_legal_marks=frozenset({"D"}),
        banned_dedupe_keys=frozenset(),
    )

    assert card.set_code == "SWSH1"


def test_sub_category_is_derived_from_name_and_rarity() -> None:
    card = project_card(
        _raw_pokemon(name="Mega Charizard ex", rarity="Special Illustration Rare"),
        set_id="swsh1",
        release_date=date(2020, 2, 7),
        standard_legal_marks=frozenset({"D"}),
        banned_dedupe_keys=frozenset(),
    )

    assert card.sub_category == ["ex", "mega"]


def test_dedupe_key_and_canonical_text_flow_from_the_shared_identity_assembly() -> None:
    card = project_card(
        _raw_pokemon(),
        set_id="swsh1",
        release_date=date(2020, 2, 7),
        standard_legal_marks=frozenset({"D"}),
        banned_dedupe_keys=frozenset(),
    )

    assert card.dedupe_key
    assert "Charizard" in card.canonical_card_text
    assert "Fire Spin" in card.canonical_card_text


def _project(raw: dict) -> CardProjection:
    return project_card(
        raw,
        set_id=str(raw["id"]).rsplit("-", 1)[0],
        release_date=date(2025, 9, 26),
        standard_legal_marks=frozenset({"H", "I", "J"}),
        banned_dedupe_keys=frozenset(),
    )


@pytest.mark.parametrize("name", ["Fire Energy", "Basic Fire Energy", "Basic  Darkness Energy", "Metal Energy"])
def test_a_textless_energy_with_a_basic_name_is_basic_energy(name: str) -> None:
    card = _project(make_tcgdex_basic_energy(name=name))

    assert card.energy_type == "Basic"
    assert card.is_standard_legal is True  # no regulation mark, still legal


def test_tcgdex_energy_type_is_not_consulted() -> None:
    assert _project(make_tcgdex_basic_energy(energyType="Special")).energy_type == "Basic"
    assert _project(make_tcgdex_special_energy(energyType="Basic")).energy_type == "Special"


def test_an_energy_with_effect_text_is_special_even_with_a_basic_name() -> None:
    assert _project(make_tcgdex_special_energy(name="Fire Energy")).energy_type == "Special"


def test_a_textless_energy_with_a_non_basic_name_fails_safe_as_special() -> None:
    card = _project(make_tcgdex_basic_energy(name="Ignition Energy", regulationMark="G"))

    assert card.energy_type == "Special"
    assert card.is_standard_legal is False  # no exception: legality falls back to its rotated mark


@pytest.mark.parametrize("name", ["Fairy Energy", "Dragon Energy", "Colorless Energy"])
def test_an_energy_outside_the_8_basic_types_is_not_basic(name: str) -> None:
    assert _project(make_tcgdex_basic_energy(name=name)).energy_type == "Special"


def test_a_non_energy_card_has_no_energy_type() -> None:
    assert _project(make_tcgdex_trainer()).energy_type is None
