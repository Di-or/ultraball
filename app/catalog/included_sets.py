# Included sets (CONTEXT.md): the explicit list of TCGdex set ids the catalog ingests.
#
# A set joins by a deliberate edit here, once TCGdex has filled it in well enough that any
# remaining gaps can be closed with catalog overrides. Then re-run the runner
# (`scripts/build_catalog.py`).
#
# Left out for now: `me06` Delta Reign (released 2026-11-06). TCGdex has no English text for
# 27 of its cards and no regulation marks (research/pre-tagging-pipeline-check.md).
INCLUDED_SETS: tuple[str, ...] = (
    # Scarlet & Violet (TCGdex series `sv`), oldest first.
    "svp",
    "sv01",
    "sve",
    "sv02",
    "sv03",
    "sv03.5",
    "sv04",
    "sv04.5",
    "sv05",
    "sv06",
    "sv06.5",
    "sv07",
    "sv08",
    "sv08.5",
    "sv09",
    "sv10",
    "sv10.5b",
    "sv10.5w",
    # Mega Evolution (TCGdex series `me`), oldest first.
    "mee",
    "me01",
    "mep",
    "me02",
    "me02.5",
    "me03",
    "me04",
    "me05",
    "30th",
)

# Sets left out of the catalog for good, because they are legal in no format (issue #146). The
# runner never ingests them, and removes any of their printings already in a database, along
# with the enrichment of card entities left with no printings.
EXCLUDED_SETS: tuple[str, ...] = (
    "mfb",  # My First Battle starter decks
    "30th-c",  # 30th Celebration Classic Collection
)
