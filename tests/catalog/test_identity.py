import pytest

from app.catalog.identity import build_card_identity
from tests.tcgdex_fixtures import load_printing


def _raw(**overrides: object) -> dict:
    base = {
        "name": "Charizard",
        "category": "Pokemon",
        "attacks": [
            {"name": "Fire Spin", "cost": ["Fire", "Fire", "Colorless", "Colorless"], "damage": 100, "effect": "Discard 2 Energy from this Pokemon."},
        ],
        "abilities": [],
        "effect": None,
    }
    base.update(overrides)
    return base


def test_identical_rules_text_collapses_to_the_same_dedupe_key() -> None:
    reprint_a = build_card_identity(_raw())
    reprint_b = build_card_identity(_raw())

    assert reprint_a.dedupe_key == reprint_b.dedupe_key


def test_distinct_effect_text_produces_distinct_dedupe_keys() -> None:
    original = build_card_identity(_raw())
    errata = build_card_identity(_raw(attacks=[{"name": "Fire Spin", "cost": ["Fire", "Fire", "Colorless", "Colorless"], "damage": 120, "effect": "Discard 2 Energy from this Pokemon."}]))

    assert original.dedupe_key != errata.dedupe_key


def test_dedupe_key_is_case_and_whitespace_insensitive() -> None:
    lower = build_card_identity(_raw(name="charizard  "))
    upper = build_card_identity(_raw(name="CHARIZARD"))

    assert lower.dedupe_key == upper.dedupe_key


def test_canonical_card_text_and_dedupe_key_share_one_assembly() -> None:
    identity = build_card_identity(_raw())

    assert "Charizard" in identity.canonical_card_text
    assert "Fire Spin" in identity.canonical_card_text
    assert "Discard 2 Energy" in identity.canonical_card_text


def test_canonical_card_text_excludes_flavor_and_filter_gate_scalars() -> None:
    identity = build_card_identity(
        _raw(hp=180, types=["Fire"], retreat=3, illustrator="Some Artist", description="A flavor blurb.")
    )

    assert "180" not in identity.canonical_card_text
    assert "Fire Spin" in identity.canonical_card_text


def test_trainer_effect_text_feeds_the_assembly() -> None:
    trainer = build_card_identity(
        {
            "name": "Boss's Orders",
            "category": "Trainer",
            "trainerType": "Supporter",
            "effect": "Switch in 1 of your opponent's Benched Pokemon to the Active Spot.",
            "attacks": [],
            "abilities": [],
        }
    )

    assert "Switch in 1 of your opponent" in trainer.canonical_card_text


def test_abilities_feed_the_assembly_and_distinguish_cards() -> None:
    with_ability = build_card_identity(
        _raw(abilities=[{"name": "Intimidating Aura", "effect": "Prevent all effects of attacks from your opponent's Pokemon VMAX."}])
    )
    without_ability = build_card_identity(_raw())

    assert with_ability.dedupe_key != without_ability.dedupe_key
    assert "Intimidating Aura" in with_ability.canonical_card_text


_SYMBOL_TYPE_NAMES = {
    "R": "Fire",
    "W": "Water",
    "G": "Grass",
    "L": "Lightning",
    "P": "Psychic",
    "F": "Fighting",
    "D": "Darkness",
    "M": "Metal",
    "N": "Dragon",
    "Y": "Fairy",
    "C": "Colorless",
}


@pytest.mark.parametrize(("letter", "type_name"), _SYMBOL_TYPE_NAMES.items())
@pytest.mark.parametrize(("open_mark", "close_mark"), [("[", "]"), ("{", "}")])
def test_energy_symbols_in_effect_text_become_type_names(
    letter: str, type_name: str, open_mark: str, close_mark: str
) -> None:
    symbol = f"{open_mark}{letter}{close_mark}"
    identity = build_card_identity(
        _raw(
            abilities=[{"name": "Charge", "effect": f"Attach a {symbol} Energy card."}],
            attacks=[{"name": "Burst", "cost": ["Colorless"], "damage": 10, "effect": f"Discard a {symbol} Energy."}],
            effect=f"Search for a {symbol} Energy.",
        )
    )

    assert symbol not in identity.canonical_card_text
    assert f"Attach a {type_name} Energy card." in identity.canonical_card_text
    assert f"Discard a {type_name} Energy." in identity.canonical_card_text
    assert f"Search for a {type_name} Energy." in identity.canonical_card_text


def test_symbol_drift_reprints_share_one_identity() -> None:
    """Mega Charizard X ex: `mep-023` writes `[R]`, `me02-013` writes `{R}` (issue #111)."""
    promo = build_card_identity(load_printing("mep-023"))
    set_printing = build_card_identity(load_printing("me02-013"))

    assert promo.dedupe_key == set_printing.dedupe_key
    assert promo.canonical_card_text == set_printing.canonical_card_text
    assert "Discard any amount of Fire Energy" in promo.canonical_card_text
