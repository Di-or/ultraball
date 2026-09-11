from datetime import date

from app.catalog.projection import project_card


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
            "energyType": "Basic",
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
