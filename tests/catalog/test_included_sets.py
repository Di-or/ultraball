from app.catalog.included_sets import EXCLUDED_SETS, INCLUDED_SETS


def test_included_sets_are_the_scarlet_violet_and_mega_evolution_sets_without_delta_reign_or_excluded_sets() -> None:
    # TCGdex's `sv` and `me` series, as of research/pre-tagging-pipeline-check.md (2026-11-08).
    assert sorted(INCLUDED_SETS) == sorted(
        [
            "svp", "sv01", "sve", "sv02", "sv03", "sv03.5", "sv04", "sv04.5", "sv05",
            "sv06", "sv06.5", "sv07", "sv08", "sv08.5", "sv09", "sv10", "sv10.5b", "sv10.5w",
            "mee", "me01", "mep", "me02", "me02.5", "me03", "me04", "me05", "30th",
        ]
    )  # fmt: skip
    assert "me06" not in INCLUDED_SETS


def test_my_first_battle_and_the_30th_classic_collection_are_excluded() -> None:
    # Legal in no format (issue #146).
    assert sorted(EXCLUDED_SETS) == ["30th-c", "mfb"]
    assert not set(EXCLUDED_SETS) & set(INCLUDED_SETS)
