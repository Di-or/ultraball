from sqlalchemy import ColumnElement, and_, exists, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.catalog.models import Card
from app.search.models import Facets, Filters, IntRange


def _representative_printings():
    """One row per `dedupe_key` — the newest printing (CONTEXT.md: Representative printing)."""
    return (
        select(Card)
        .distinct(Card.dedupe_key)
        .order_by(Card.dedupe_key, Card.release_date.desc(), Card.ingested_at.desc())
        .cte("representative_printing")
    )


def _range_predicate(column: ColumnElement, rng: IntRange) -> ColumnElement:
    conditions = []
    if rng.gte is not None:
        conditions.append(column >= rng.gte)
    if rng.lte is not None:
        conditions.append(column <= rng.lte)
    return and_(*conditions) if conditions else true()


def _attack_cost_predicate(rep: type[Card], rng: IntRange) -> ColumnElement:
    """Any-attack semantics: some attack's total cost falls in range."""
    unnested = func.unnest(rep.attack_costs).table_valued("cost").render_derived()
    conditions = []
    if rng.gte is not None:
        conditions.append(unnested.c.cost >= rng.gte)
    if rng.lte is not None:
        conditions.append(unnested.c.cost <= rng.lte)
    return exists(select(1).select_from(unnested).where(*conditions))


def _build_predicates(rep: type[Card], filters: Filters, facets: Facets) -> list[ColumnElement]:
    """Fields conjoin (AND); a multi-valued field disjoins (OR/overlap) within itself."""
    predicates: list[ColumnElement] = []

    if filters.format == "standard":
        predicates.append(rep.is_standard_legal.is_(True))
    if filters.category is not None:
        predicates.append(rep.category == filters.category)
    if filters.stage is not None:
        predicates.append(rep.stage == filters.stage)
    if filters.trainer_type is not None:
        predicates.append(rep.trainer_type == filters.trainer_type)
    if filters.energy_type is not None:
        predicates.append(rep.energy_type == filters.energy_type)
    if filters.set_id is not None:
        predicates.append(rep.set_id == filters.set_id)
    if filters.types:
        predicates.append(rep.types.op("&&")(filters.types))
    if filters.sub_category:
        predicates.append(rep.sub_category.op("&&")(filters.sub_category))
    if filters.hp is not None:
        predicates.append(_range_predicate(rep.hp, filters.hp))
    if filters.retreat is not None:
        predicates.append(_range_predicate(rep.retreat, filters.retreat))
    if filters.attack_cost is not None:
        predicates.append(_attack_cost_predicate(rep, filters.attack_cost))

    if facets.regulation_mark:
        predicates.append(rep.regulation_mark.in_(facets.regulation_mark))
    if facets.rarity:
        predicates.append(rep.rarity.in_(facets.rarity))

    return predicates


async def run_search(
    session: AsyncSession,
    filters: Filters,
    facets: Facets,
    *,
    limit: int,
    offset: int,
    keyword: str | None = None,
) -> tuple[list[Card], int]:
    """The gated candidate pool (CONTEXT.md: Candidate pool), name-sorted (Faceted mode).

    `keyword` is set only on a degraded parse (CONTEXT.md: Parse object) — a plain
    substring match on `name`, layered onto the gate rather than replacing it.
    No concept/tags ranking here — this is the plain conventional gate; the
    semantic/tag-match ranking paths (#23/#24/#25) rank *within* this same pool.
    """
    rep = aliased(Card, _representative_printings())
    predicates = _build_predicates(rep, filters, facets)
    if keyword:
        predicates.append(rep.name.ilike(f"%{keyword}%"))

    gated = select(rep).where(*predicates)

    total = await session.scalar(select(func.count()).select_from(gated.subquery()))

    paged = gated.order_by(rep.name.asc(), rep.dedupe_key.asc()).limit(limit).offset(offset)
    results = list(await session.scalars(paged))

    return results, total or 0
