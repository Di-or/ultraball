from tests.factories import make_card as _card

from app.catalog.deck_validation import DeckLine, validate_deck


def _basic_pokemon(**overrides: object) -> object:
    overrides.setdefault("category", "Pokemon")
    overrides.setdefault("stage", "Basic")
    overrides.setdefault("is_standard_legal", True)
    return _card(**overrides)


def _basic_energy(**overrides: object) -> object:
    overrides.setdefault("category", "Energy")
    overrides.setdefault("energy_type", "Basic")
    overrides.setdefault("stage", None)
    overrides.setdefault("is_standard_legal", True)
    overrides.setdefault("name", "Fire Energy")
    return _card(**overrides)


def test_a_legal_deck_has_no_violations() -> None:
    lines = [
        DeckLine(card=_basic_pokemon(id="p1", dedupe_key="p1", name="Pikachu"), count=4),
        DeckLine(card=_basic_energy(id="e1", dedupe_key="e1"), count=56),
    ]

    report = validate_deck(lines)

    assert report.legal is True
    assert report.violations == []
    assert report.counts.pokemon == 4
    assert report.counts.energy == 56
    assert report.counts.trainer == 0
    assert report.counts.total == 60


def test_deck_size_must_be_exactly_60() -> None:
    lines = [DeckLine(card=_basic_pokemon(id="p1", dedupe_key="p1"), count=10)]

    report = validate_deck(lines)

    assert report.legal is False
    codes = [v.code for v in report.violations]
    assert "deck_size" in codes


def test_more_than_4_copies_of_a_name_is_flagged() -> None:
    lines = [
        DeckLine(card=_basic_pokemon(id="p1", dedupe_key="p1", name="Riolu"), count=3),
        DeckLine(card=_basic_pokemon(id="p2", dedupe_key="p2", name="Riolu"), count=3),
    ]

    report = validate_deck(lines)

    violation = next(v for v in report.violations if v.code == "four_copy_limit")
    assert sorted(violation.cards) == ["p1", "p2"]


def test_two_distinct_names_are_capped_independently() -> None:
    """Two 'Riolu' printings share the 4-copy cap; 'Charizard ex' is its own name."""
    lines = [
        DeckLine(card=_basic_pokemon(id="p1", dedupe_key="p1", name="Riolu"), count=4),
        DeckLine(card=_basic_pokemon(id="p2", dedupe_key="p2", name="Charizard ex"), count=4),
    ]

    report = validate_deck(lines)

    assert [v for v in report.violations if v.code == "four_copy_limit"] == []


def test_basic_energy_is_exempt_from_the_4_copy_rule() -> None:
    lines = [DeckLine(card=_basic_energy(id="e1", dedupe_key="e1"), count=56)]

    report = validate_deck(lines)

    assert [v for v in report.violations if v.code == "four_copy_limit"] == []


def test_special_energy_is_not_exempt_from_the_4_copy_rule() -> None:
    lines = [
        DeckLine(
            card=_card(
                category="Energy",
                energy_type="Special",
                stage=None,
                name="Double Turbo Energy",
                id="e1",
                dedupe_key="e1",
                is_standard_legal=True,
            ),
            count=5,
        )
    ]

    report = validate_deck(lines)

    codes = [v.code for v in report.violations]
    assert "four_copy_limit" in codes


def test_non_standard_legal_cards_are_flagged() -> None:
    lines = [DeckLine(card=_basic_pokemon(id="p1", dedupe_key="p1", is_standard_legal=False), count=4)]

    report = validate_deck(lines)

    violation = next(v for v in report.violations if v.code == "not_standard_legal")
    assert violation.cards == ["p1"]


def test_deck_with_no_basic_pokemon_is_flagged() -> None:
    lines = [DeckLine(card=_basic_energy(id="e1", dedupe_key="e1"), count=60)]

    report = validate_deck(lines)

    codes = [v.code for v in report.violations]
    assert "no_basic_pokemon" in codes


def test_more_than_one_ace_spec_is_flagged() -> None:
    lines = [
        DeckLine(
            card=_card(
                category="Trainer",
                trainer_type="Item",
                stage=None,
                sub_category=["ace-spec"],
                name="Prime Catcher",
                id="t1",
                dedupe_key="t1",
                is_standard_legal=True,
            ),
            count=1,
        ),
        DeckLine(
            card=_card(
                category="Trainer",
                trainer_type="Item",
                stage=None,
                sub_category=["ace-spec"],
                name="Neutralization Zone",
                id="t2",
                dedupe_key="t2",
                is_standard_legal=True,
            ),
            count=1,
        ),
    ]

    report = validate_deck(lines)

    violation = next(v for v in report.violations if v.code == "ace_spec_limit")
    assert sorted(violation.cards) == ["t1", "t2"]


def test_unresolved_printing_ids_are_flagged_and_counted_toward_deck_size() -> None:
    lines = [DeckLine(card=_basic_pokemon(id="p1", dedupe_key="p1"), count=59)]

    report = validate_deck(lines, unresolved_printing_ids=["does-not-exist"])

    violation = next(v for v in report.violations if v.code == "unknown_printing")
    assert violation.cards == ["does-not-exist"]
    assert report.counts.total == 60
