from sqlalchemy import UnaryExpression

from app.catalog.models import Card


def representative_order(card: type[Card]) -> tuple[UnaryExpression, ...]:
    """Printings of one card entity, best first: the first is its representative printing
    (CONTEXT.md: Representative printing).

    Newest regulation mark (single letters, so alphabetical is chronological; unmarked last),
    then newest release date, then having an image, then printing id ascending, a stable
    tie-break. Release date and ingest time are not enough on their own: a promo set shares one
    series-wide date, and one ingest run stamps every printing with the same time.

    `card` is `Card` or an alias of it. For `DISTINCT ON (dedupe_key)`, put `dedupe_key` first.
    """
    return (
        card.regulation_mark.desc().nulls_last(),
        card.release_date.desc(),
        card.image.is_not(None).desc(),
        card.id.asc(),
    )
