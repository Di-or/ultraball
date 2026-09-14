from app.catalog.ptcgl_import import parse_ptcgl


def test_parses_a_card_line_with_set_code_and_local_id() -> None:
    lines = parse_ptcgl("4 Charmander OBF 10")

    assert len(lines) == 1
    assert lines[0].count == 4
    assert lines[0].name == "Charmander"
    assert lines[0].set_code == "OBF"
    assert lines[0].local_id == "10"


def test_parses_a_bare_basic_energy_line() -> None:
    lines = parse_ptcgl("8 Basic Fire Energy")

    assert len(lines) == 1
    assert lines[0].count == 8
    assert lines[0].name == "Fire Energy"
    assert lines[0].set_code is None
    assert lines[0].local_id is None


def test_skips_section_headers_blank_lines_and_totals() -> None:
    text = """
    Pokémon: 12
    4 Charmander OBF 10

    Trainer Cards: 1
    1 Iono PAF 80

    Energy: 8
    8 Basic Fire Energy

    Total Cards: 21
    """

    lines = parse_ptcgl(text)

    assert [line.name for line in lines] == ["Charmander", "Iono", "Fire Energy"]


def test_multi_word_card_names_are_preserved() -> None:
    lines = parse_ptcgl("2 Charizard ex OBF 125")

    assert lines[0].name == "Charizard ex"
    assert lines[0].set_code == "OBF"
    assert lines[0].local_id == "125"


def test_set_code_is_uppercased() -> None:
    lines = parse_ptcgl("4 Charmander obf 10")

    assert lines[0].set_code == "OBF"
