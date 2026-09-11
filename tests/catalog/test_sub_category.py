from app.catalog.sub_category import derive_sub_category


def test_plain_pokemon_has_no_sub_category() -> None:
    assert derive_sub_category(name="Charizard", rarity="Rare Holo") == []


def test_ex_suffix_yields_ex() -> None:
    assert derive_sub_category(name="Charizard ex", rarity="Double Rare") == ["ex"]


def test_mega_prefix_encodes_mega_as_a_subset_of_ex() -> None:
    assert derive_sub_category(name="Mega Charizard ex", rarity="Special Illustration Rare") == ["ex", "mega"]


def test_ace_spec_rarity_yields_ace_spec() -> None:
    assert derive_sub_category(name="Prime Catcher", rarity="ACE SPEC Rare") == ["ace-spec"]


def test_ace_spec_rarity_is_case_insensitive() -> None:
    assert derive_sub_category(name="Prime Catcher", rarity="ace spec rare") == ["ace-spec"]


def test_missing_rarity_does_not_error() -> None:
    assert derive_sub_category(name="Charizard", rarity=None) == []


def test_owner_prefixed_ex_still_detected() -> None:
    assert derive_sub_category(name="Larry's Charizard ex", rarity="Ultra Rare") == ["ex"]
