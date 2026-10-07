import re
from pathlib import Path

from app.enrichment.taxonomy import FUNCTIONAL_TAGS, TAG_DEFINITIONS, TAG_EXAMPLES, TAXONOMY_VERSION

# The doc for the current taxonomy version; earlier versions' docs stay as a record.
_TAXONOMY_DOC = Path(__file__).parents[2] / "research" / f"tag-taxonomy-{TAXONOMY_VERSION}.md"

# A tag row in one of the doc's family tables: | `tag` | definition | example |
_TAG_ROW = re.compile(r"^\| `(?P<tag>[a-z-]+)` \| (?P<definition>.+?) \| (?P<examples>.+?) \|$")

# Main Scarlet & Violet and Mega Evolution sets only (no promos), e.g. sv01-181, sv03.5-108, me02.5-050.
_SV_OR_ME_CARD_ID = re.compile(r"^(sv\d{2}(\.5[wb]?)?|me\d{2}(\.5)?)-\d{3}$")


def _doc_rows() -> dict[str, tuple[str, str]]:
    rows = {}
    for line in _TAXONOMY_DOC.read_text(encoding="utf-8").splitlines():
        if match := _TAG_ROW.match(line):
            rows[match["tag"]] = (match["definition"], match["examples"])
    return rows


def test_functional_tags_are_derived_from_the_definitions() -> None:
    assert FUNCTIONAL_TAGS == set(TAG_DEFINITIONS)
    assert len(FUNCTIONAL_TAGS) == 28


def test_every_tag_has_a_definition_and_a_current_range_example() -> None:
    assert set(TAG_EXAMPLES) == set(TAG_DEFINITIONS)
    for tag, definition in TAG_DEFINITIONS.items():
        assert definition.strip(), tag
        assert TAG_EXAMPLES[tag], tag
        for example in TAG_EXAMPLES[tag]:
            assert example.name.strip(), tag
            assert _SV_OR_ME_CARD_ID.match(example.card_id), (tag, example.card_id)


def test_taxonomy_doc_definitions_match_the_code_word_for_word() -> None:
    rows = _doc_rows()

    assert set(rows) == set(TAG_DEFINITIONS)
    for tag, (definition, _) in rows.items():
        assert definition == TAG_DEFINITIONS[tag], tag


def test_taxonomy_doc_examples_match_the_code() -> None:
    for tag, (_, examples) in _doc_rows().items():
        expected = ", ".join(f"{example.name} (`{example.card_id}`)" for example in TAG_EXAMPLES[tag])
        assert examples == expected, tag
