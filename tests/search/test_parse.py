from app.search.parse import enforce_filters, normalize_query


def test_normalize_query_lowercases_and_collapses_whitespace() -> None:
    assert normalize_query("  Energy   Accel \n Under 130 HP  ") == "energy accel under 130 hp"


def test_enforce_filters_keeps_valid_enum_values() -> None:
    filters = enforce_filters({"category": "Pokemon", "stage": "Basic"})

    assert filters.category == "Pokemon"
    assert filters.stage == "Basic"


def test_enforce_filters_drops_an_invalid_enum_value() -> None:
    filters = enforce_filters({"category": "NotACategory"})

    assert filters.category is None


def test_enforce_filters_drops_an_unknown_field() -> None:
    filters = enforce_filters({"nonsense_field": "whatever"})

    assert filters.model_dump(exclude={"format"}) == {
        "category": None,
        "sub_category": None,
        "types": None,
        "hp": None,
        "retreat": None,
        "attack_cost": None,
        "stage": None,
        "trainer_type": None,
        "energy_type": None,
        "set_id": None,
    }


def test_enforce_filters_defaults_format_to_standard_when_absent() -> None:
    filters = enforce_filters({})

    assert filters.format == "standard"


def test_enforce_filters_parses_a_range() -> None:
    filters = enforce_filters({"hp": {"lte": 130}})

    assert filters.hp is not None
    assert filters.hp.lte == 130
    assert filters.hp.gte is None


def test_enforce_filters_drops_a_range_with_a_non_numeric_bound() -> None:
    filters = enforce_filters({"retreat": {"lte": "a lot"}})

    assert filters.retreat is None


def test_enforce_filters_drops_an_invalid_element_in_a_list_field() -> None:
    filters = enforce_filters({"sub_category": ["ex", "not-a-sub-category"]})

    assert filters.sub_category is None
