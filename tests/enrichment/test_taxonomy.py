import re
from pathlib import Path

from app.enrichment.taxonomy import (
    BENCH_DAMAGE_TAGS,
    FUNCTIONAL_TAGS,
    TAG_DEFINITIONS,
    TAG_EXAMPLES,
    TAXONOMY_VERSION,
    TWO_TAG_RULES,
    TagExample,
    render_tag_glossary,
    render_two_tag_rules,
)

# The doc for the current taxonomy version; earlier versions' docs stay as a record.
_TAXONOMY_DOC = Path(__file__).parents[2] / "research" / f"tag-taxonomy-{TAXONOMY_VERSION}.md"

# A tag row in one of the doc's family tables: | `tag` | definition | example |
_TAG_ROW = re.compile(r"^\| `(?P<tag>[a-z-]+)` \| (?P<definition>.+?) \| (?P<examples>.+?) \|$")

# Main Scarlet & Violet and Mega Evolution sets only (no promos), e.g. sv01-181, sv03.5-108, me02.5-050.
_SV_OR_ME_CARD_ID = re.compile(r"^(sv\d{2}(\.5[wb]?)?|me\d{2}(\.5)?)-\d{3}$")


# A row in the doc's "Effects that carry two tags" table: | effect | `a` + `b` |
_TWO_TAG_ROW = re.compile(r"^\| (?P<effect>.+?) \| `(?P<first>[a-z-]+)` \+ `(?P<second>[a-z-]+)` \|$")


def _doc_two_tag_rows() -> list[tuple[str, tuple[str, str]]]:
    text = _TAXONOMY_DOC.read_text(encoding="utf-8")
    section = text.split("## Effects that carry two tags", 1)[1].split("\n## ", 1)[0]
    return [
        (match["effect"], (match["first"], match["second"]))
        for line in section.splitlines()
        if (match := _TWO_TAG_ROW.match(line))
    ]


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


def test_the_glossary_says_coin_flips_dont_make_damage_scale() -> None:
    # #104: "80 damage for each heads" (Toedscruel sv01-026) was tagged `damage-scaling`, so a
    # search for attackers that grow with Energy would also return coin-flip attackers.
    damage_scaling_line = next(
        line for line in render_tag_glossary().splitlines() if line.startswith("- damage-scaling")
    )

    assert "Coin flips aren't a game-state count." in damage_scaling_line


def test_each_two_tag_rule_names_two_different_tags_from_the_taxonomy() -> None:
    assert TWO_TAG_RULES
    for rule in TWO_TAG_RULES:
        assert rule.effect.strip()
        assert len(set(rule.tags)) == 2, rule
        assert set(rule.tags) <= FUNCTIONAL_TAGS, rule


def test_taxonomy_doc_two_tag_rules_match_the_code_word_for_word() -> None:
    assert _doc_two_tag_rows() == [(rule.effect, rule.tags) for rule in TWO_TAG_RULES]


def test_the_two_tag_block_lists_every_rule_with_both_tags() -> None:
    block = render_two_tag_rules()

    for rule in TWO_TAG_RULES:
        assert f"- {rule.effect}: `{rule.tags[0]}` + `{rule.tags[1]}`." in block


def test_taxonomy_doc_definitions_match_the_code_word_for_word() -> None:
    rows = _doc_rows()

    assert set(rows) == set(TAG_DEFINITIONS)
    for tag, (definition, _) in rows.items():
        assert definition == TAG_DEFINITIONS[tag], tag


def test_taxonomy_doc_examples_match_the_code() -> None:
    for tag, (_, examples) in _doc_rows().items():
        expected = ", ".join(_doc_example(example) for example in TAG_EXAMPLES[tag])
        assert examples == expected, tag
