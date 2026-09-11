from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Card
from app.search.models import Facets, Filters, IntRange
from app.search.queries import run_search


def _card(**overrides: object) -> Card:
    base = dict(
        id=overrides.pop("id", "swsh1-1"),
        set_id="swsh1",
        local_id="1",
        name="Charizard",
        category="Pokemon",
        hp=170,
        types=["Fire"],
        stage="Stage 2",
        evolve_from="Charmeleon",
        retreat=3,
        regulation_mark="H",
        rarity="Rare Holo",
        trainer_type=None,
        energy_type=None,
        attacks=[],
        abilities=[],
        attack_costs=[4],
        sub_category=[],
        dedupe_key=overrides.pop("dedupe_key", "charizard-1"),
        canonical_card_text="Charizard",
        is_standard_legal=True,
        release_date=date(2023, 1, 1),
    )
    base.update(overrides)
    return Card(**base)


async def _seed(session: AsyncSession, *cards: Card) -> None:
    session.add_all(cards)
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
