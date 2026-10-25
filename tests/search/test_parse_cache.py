from app.catalog.set_models import CatalogSet
from app.search.parse_cache import make_cache_key

_TWM = CatalogSet(id="sv06", code="TWM", name="Twilight Masquerade")
_SVI = CatalogSet(id="sv01", code="SVI", name="Scarlet & Violet")


def test_same_set_list_gives_the_same_cache_key() -> None:
    assert make_cache_key("twm supporters", "v1", (_TWM, _SVI)) == make_cache_key("twm supporters", "v1", (_SVI, _TWM))


def test_adding_a_set_changes_the_cache_key() -> None:
    # A newly ingested set must invalidate cached parses without a PARSE_VERSION bump.
    assert make_cache_key("twm supporters", "v1", (_TWM,)) != make_cache_key("twm supporters", "v1", (_TWM, _SVI))


def test_renaming_a_set_changes_the_cache_key() -> None:
    renamed = CatalogSet(id="sv06", code="TWM", name="")
    assert make_cache_key("twm supporters", "v1", (_TWM,)) != make_cache_key("twm supporters", "v1", (renamed,))


def test_parse_version_still_changes_the_cache_key() -> None:
    assert make_cache_key("twm supporters", "v1", (_TWM,)) != make_cache_key("twm supporters", "v2", (_TWM,))
