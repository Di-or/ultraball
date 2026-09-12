from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Card
from app.enrichment import status
from app.enrichment.models import CardEnrichment
from app.search.models import Facets, Filters, IntRange
from app.search.queries import run_search, run_tag_match_search
from tests.factories import make_card as _card
from tests.factories import make_enrichment as _enrichment


async def _seed(session: AsyncSession, *rows: Card | CardEnrichment) -> None:
    session.add_all(rows)
    await session.commit()


async def test_empty_filters_return_the_full_standard_legal_gate(db_session: AsyncSession) -> None:
    await _seed(db_session, _card(id="a", dedupe_key="a"), _card(id="b", dedupe_key="b", name="Blastoise"))

    results, total = await run_search(db_session, Filters(), Facets(), limit=30, offset=0)

    assert total == 2
    assert {r.name for r in results} == {"Charizard", "Blastoise"}


async def test_is_standard_legal_defaults_on(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="legal", dedupe_key="legal", is_standard_legal=True),
        _card(id="rotated", dedupe_key="rotated", name="Rotated Mon", is_standard_legal=False),
    )

    results, total = await run_search(db_session, Filters(), Facets(), limit=30, offset=0)

    assert total == 1
    assert results[0].name == "Charizard"


async def test_format_none_opts_out_of_the_standard_gate(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="legal", dedupe_key="legal", is_standard_legal=True),
        _card(id="rotated", dedupe_key="rotated", name="Rotated Mon", is_standard_legal=False),
    )

    _, total = await run_search(db_session, Filters(format=None), Facets(), limit=30, offset=0)

    assert total == 2


async def test_fields_conjoin_with_and(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="a", dedupe_key="a", category="Pokemon", stage="Stage 2"),
        _card(id="b", dedupe_key="b", name="Bulbasaur", category="Pokemon", stage="Basic"),
    )

    _, total = await run_search(
        db_session, Filters(category="Pokemon", stage="Stage 2"), Facets(), limit=30, offset=0
    )

    assert total == 1


async def test_types_disjoin_within_the_field_via_overlap(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="a", dedupe_key="a", types=["Fire"]),
        _card(id="b", dedupe_key="b", name="Blastoise", types=["Water"]),
        _card(id="c", dedupe_key="c", name="Pikachu", types=["Lightning"]),
    )

    results, total = await run_search(db_session, Filters(types=["Fire", "Water"]), Facets(), limit=30, offset=0)

    assert total == 2
    assert {r.name for r in results} == {"Charizard", "Blastoise"}


async def test_sub_category_overlap_encodes_mega_subset_of_ex(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="a", dedupe_key="a", name="Charizard ex", sub_category=["ex"]),
        _card(id="b", dedupe_key="b", name="Mega Charizard ex", sub_category=["ex", "mega"]),
        _card(id="c", dedupe_key="c", name="Pikachu", sub_category=[]),
    )

    results, _total = await run_search(db_session, Filters(sub_category=["ex"]), Facets(), limit=30, offset=0)

    assert {r.name for r in results} == {"Charizard ex", "Mega Charizard ex"}


async def test_attack_cost_matches_any_attack_in_range(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="a", dedupe_key="a", attack_costs=[1, 3]),
        _card(id="b", dedupe_key="b", name="Blastoise", attack_costs=[5]),
    )

    results, _total = await run_search(
        db_session, Filters(attack_cost=IntRange(gte=1, lte=2)), Facets(), limit=30, offset=0
    )

    assert {r.name for r in results} == {"Charizard"}


async def test_facets_filter_by_regulation_mark_and_rarity(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="a", dedupe_key="a", regulation_mark="H", rarity="Rare Holo"),
        _card(id="b", dedupe_key="b", name="Blastoise", regulation_mark="G", rarity="Common"),
    )

    results, _total = await run_search(
        db_session, Filters(), Facets(regulation_mark=["H"]), limit=30, offset=0
    )

    assert {r.name for r in results} == {"Charizard"}


async def test_empty_gate_returns_empty_result_not_an_error(db_session: AsyncSession) -> None:
    await _seed(db_session, _card(id="a", dedupe_key="a"))

    results, total = await run_search(db_session, Filters(category="Energy"), Facets(), limit=30, offset=0)

    assert results == []
    assert total == 0


async def test_only_the_representative_printing_is_returned_per_dedupe_key(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="old", dedupe_key="shared", release_date=date(1999, 1, 1), regulation_mark="D"),
        _card(id="new", dedupe_key="shared", release_date=date(2023, 1, 1), regulation_mark="H"),
    )

    results, total = await run_search(db_session, Filters(), Facets(), limit=30, offset=0)

    assert total == 1
    assert results[0].id == "new"


async def test_faceted_mode_sorts_name_a_to_z_then_dedupe_key(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="a", dedupe_key="z-key", name="Zubat"),
        _card(id="b", dedupe_key="a-key", name="Abra"),
        _card(id="c", dedupe_key="m-key", name="Machop"),
    )

    results, _total = await run_search(db_session, Filters(), Facets(), limit=30, offset=0)

    assert [r.name for r in results] == ["Abra", "Machop", "Zubat"]


async def test_pagination_limits_page_but_total_reflects_full_gate(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="a", dedupe_key="a", name="Abra"),
        _card(id="b", dedupe_key="b", name="Bulbasaur"),
        _card(id="c", dedupe_key="c", name="Charizard2"),
    )

    results, total = await run_search(db_session, Filters(), Facets(), limit=2, offset=1)

    assert total == 3
    assert [r.name for r in results] == ["Bulbasaur", "Charizard2"]


async def test_tag_match_ranks_by_overlap_count_desc(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="a", dedupe_key="a", name="Charizard"),
        _enrichment(dedupe_key="a", tags=["draw", "search", "recovery"]),
        _card(id="b", dedupe_key="b", name="Blastoise"),
        _enrichment(dedupe_key="b", tags=["draw"]),
        _card(id="c", dedupe_key="c", name="Pikachu"),
        _enrichment(dedupe_key="c", tags=["gust"]),
    )

    results, total = await run_tag_match_search(
        db_session, Filters(), Facets(), ["draw", "search"], limit=30, offset=0
    )

    assert total == 2
    assert [card.name for card, _matched in results] == ["Charizard", "Blastoise"]


async def test_tag_match_is_any_of_not_jaccard(db_session: AsyncSession) -> None:
    """A richly-tagged staple that overlaps on one tag still outranks a card with fewer tags."""
    await _seed(
        db_session,
        _card(id="a", dedupe_key="a", name="Staple", release_date=date(2020, 1, 1)),
        _enrichment(dedupe_key="a", tags=["draw", "search", "recovery", "healing", "gust"]),
        _card(id="b", dedupe_key="b", name="OneTrick", release_date=date(2020, 1, 1)),
        _enrichment(dedupe_key="b", tags=["draw"]),
    )

    results, _total = await run_tag_match_search(
        db_session, Filters(), Facets(), ["draw"], limit=30, offset=0
    )

    assert {card.name for card, _matched in results} == {"Staple", "OneTrick"}


async def test_tag_match_excludes_cards_with_no_overlap(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="a", dedupe_key="a", name="Charizard"),
        _enrichment(dedupe_key="a", tags=["gust"]),
    )

    results, total = await run_tag_match_search(
        db_session, Filters(), Facets(), ["draw"], limit=30, offset=0
    )

    assert total == 0
    assert results == []


async def test_tag_match_equal_overlap_ties_broken_by_release_date_desc(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="old", dedupe_key="old", name="Older", release_date=date(2018, 1, 1)),
        _enrichment(dedupe_key="old", tags=["draw"]),
        _card(id="new", dedupe_key="new", name="Newer", release_date=date(2023, 1, 1)),
        _enrichment(dedupe_key="new", tags=["draw"]),
    )

    results, _total = await run_tag_match_search(
        db_session, Filters(), Facets(), ["draw"], limit=30, offset=0
    )

    assert [card.name for card, _matched in results] == ["Newer", "Older"]


async def test_tag_match_reports_which_query_tags_each_card_carries(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="a", dedupe_key="a", name="Charizard"),
        _enrichment(dedupe_key="a", tags=["draw", "gust"]),
    )

    results, _total = await run_tag_match_search(
        db_session, Filters(), Facets(), ["draw", "search"], limit=30, offset=0
    )

    assert results[0][1] == ["draw"]


async def test_tag_match_respects_the_gate_filters(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="a", dedupe_key="a", name="Charizard", is_standard_legal=True),
        _enrichment(dedupe_key="a", tags=["draw"]),
        _card(id="b", dedupe_key="b", name="Rotated", is_standard_legal=False),
        _enrichment(dedupe_key="b", tags=["draw"]),
    )

    results, total = await run_tag_match_search(
        db_session, Filters(), Facets(), ["draw"], limit=30, offset=0
    )

    assert total == 1
    assert results[0][0].name == "Charizard"


async def test_tag_match_only_the_representative_printing_is_ranked(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="old", dedupe_key="shared", release_date=date(1999, 1, 1), regulation_mark="D"),
        _card(id="new", dedupe_key="shared", release_date=date(2023, 1, 1), regulation_mark="H"),
        _enrichment(dedupe_key="shared", tags=["draw"]),
    )

    results, total = await run_tag_match_search(
        db_session, Filters(), Facets(), ["draw"], limit=30, offset=0
    )

    assert total == 1
    assert results[0][0].id == "new"


async def test_tag_match_pagination_limits_page_but_total_reflects_full_pool(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="a", dedupe_key="a", name="Abra", release_date=date(2023, 1, 3)),
        _enrichment(dedupe_key="a", tags=["draw"]),
        _card(id="b", dedupe_key="b", name="Bulbasaur", release_date=date(2023, 1, 2)),
        _enrichment(dedupe_key="b", tags=["draw"]),
        _card(id="c", dedupe_key="c", name="Charizard2", release_date=date(2023, 1, 1)),
        _enrichment(dedupe_key="c", tags=["draw"]),
    )

    results, total = await run_tag_match_search(
        db_session, Filters(), Facets(), ["draw"], limit=2, offset=1
    )

    assert total == 3
    assert [card.name for card, _matched in results] == ["Bulbasaur", "Charizard2"]


async def test_tag_match_excludes_enrichment_rows_not_yet_completed(db_session: AsyncSession) -> None:
    await _seed(
        db_session,
        _card(id="a", dedupe_key="a", name="Completed"),
        _enrichment(dedupe_key="a", tags=["draw"], status=status.COMPLETED),
        _card(id="b", dedupe_key="b", name="Pending"),
        _enrichment(dedupe_key="b", tags=["draw"], status=status.PENDING),
        _card(id="c", dedupe_key="c", name="Failed"),
        _enrichment(dedupe_key="c", tags=["draw"], status=status.FAILED),
    )

    results, total = await run_tag_match_search(
        db_session, Filters(), Facets(), ["draw"], limit=30, offset=0
    )

    assert total == 1
    assert [card.name for card, _matched in results] == ["Completed"]


async def test_tag_match_pool_is_capped_at_200(db_session: AsyncSession) -> None:
    rows: list[Card | CardEnrichment] = []
    for i in range(210):
        dedupe_key = f"card-{i:03d}"
        rows.append(_card(id=dedupe_key, dedupe_key=dedupe_key, name=f"Card {i:03d}", release_date=date(2020, 1, 1)))
        rows.append(_enrichment(dedupe_key=dedupe_key, tags=["draw"]))
    await _seed(db_session, *rows)

    results, total = await run_tag_match_search(
        db_session, Filters(), Facets(), ["draw"], limit=250, offset=0
    )

    assert total == 200
    assert len(results) == 200
