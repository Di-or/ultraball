import re
from pathlib import Path

from app.enrichment.taxonomy import (
    BENCH_DAMAGE_TAGS,
    FUNCTIONAL_TAGS,
    TAG_DEFINITIONS,
    TAG_EXAMPLES,
    TAXONOMY_VERSION,
    TagExample,
    render_tag_glossary,
)

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


def _doc_example(example: TagExample) -> str:
    """How the doc cites an example: `Name (`id`)`, or `Name (`id`, also `a`, `b`)`."""
    also = "".join(f", {'also ' if i == 0 else ''}`{tag}`" for i, tag in enumerate(example.also))
    return f"{example.name} (`{example.card_id}`{also})"


def test_functional_tags_are_derived_from_the_definitions() -> None:
    assert FUNCTIONAL_TAGS == set(TAG_DEFINITIONS)
    assert len(FUNCTIONAL_TAGS) == 30


def test_v5_splits_prevention_adds_boosts_and_movement_and_merges_the_energy_tags() -> None:
    # #103: effects of attacks (damage counters included) are split from damage, flat damage
    # bonuses and moving Energy get tags, and Energy search and recovery fold into the general tags.
    assert {"damage-prevention", "effect-prevention", "damage-boost", "energy-movement"} <= FUNCTIONAL_TAGS
    assert not {"energy-search", "energy-recovery"} & FUNCTIONAL_TAGS


def test_every_tag_has_a_definition_and_a_current_range_example() -> None:
    assert set(TAG_EXAMPLES) == set(TAG_DEFINITIONS)
    for tag, definition in TAG_DEFINITIONS.items():
        assert definition.strip(), tag
        assert TAG_EXAMPLES[tag], tag
        for example in TAG_EXAMPLES[tag]:
            assert example.name.strip(), tag
            assert _SV_OR_ME_CARD_ID.match(example.card_id), (tag, example.card_id)


def test_no_card_is_the_example_for_two_tags() -> None:
    # Each example carries only its own tag, so a card can illustrate at most one.
    card_ids = [example.card_id for examples in TAG_EXAMPLES.values() for example in examples]
    assert len(card_ids) == len(set(card_ids))


def test_only_the_bench_damage_family_examples_carry_other_tags() -> None:
    # Nearly anything `multi-target` is also `bench-reach` (there is one Active), so these three
    # tags' examples may carry each other's tags, and name them. Every other example stays single-tag.
    assert BENCH_DAMAGE_TAGS == {"bench-reach", "multi-target", "counter-placement"}
    for tag, examples in TAG_EXAMPLES.items():
        for example in examples:
            if tag in BENCH_DAMAGE_TAGS:
                assert set(example.also) <= BENCH_DAMAGE_TAGS - {tag}, (tag, example)
            else:
                assert example.also == (), (tag, example)


def test_the_glossary_names_the_other_tags_an_example_carries() -> None:
    glossary = render_tag_glossary()

    assert "Examples: Lapras (also bench-reach), Regice (also bench-reach)." in glossary
    assert "Examples: Golbat, Elekid." in glossary


def test_taxonomy_doc_definitions_match_the_code_word_for_word() -> None:
    rows = _doc_rows()

    assert set(rows) == set(TAG_DEFINITIONS)
    for tag, (definition, _) in rows.items():
        assert definition == TAG_DEFINITIONS[tag], tag


def test_taxonomy_doc_examples_match_the_code() -> None:
    for tag, (_, examples) in _doc_rows().items():
        expected = ", ".join(_doc_example(example) for example in TAG_EXAMPLES[tag])
        assert examples == expected, tag
