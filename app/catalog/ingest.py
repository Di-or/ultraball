from collections.abc import Collection, Set
from dataclasses import asdict

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.legality_config import BANNED_DEDUPE_KEYS, STANDARD_LEGAL_MARKS
from app.catalog.models import Card, RawCard
from app.catalog.projection import project_card
from app.clients.catalog_client import CatalogClient


async def run_ingest(
    session: AsyncSession,
    catalog_client: CatalogClient,
    set_id: str,
    *,
    standard_legal_marks: Collection[str] = STANDARD_LEGAL_MARKS,
    banned_dedupe_keys: Set[str] = BANNED_DEDUPE_KEYS,
) -> None:
    """Crawl one set and project it into `raw_cards` + `cards`.

    Refresh is set-driven: every printing in the snapshot is upserted by id, so
    re-running ingest on a set (new cards, or a legality re-derive) is idempotent.
    """
    snapshot = await catalog_client.fetch_set(set_id)

    for raw in snapshot.cards:
        await session.execute(
            insert(RawCard)
            .values(id=raw["id"], set_id=snapshot.set_id, raw=raw)
            .on_conflict_do_update(index_elements=[RawCard.id], set_={"raw": raw, "set_id": snapshot.set_id})
        )

        card = project_card(
            raw,
            set_id=snapshot.set_id,
            release_date=snapshot.release_date,
            standard_legal_marks=standard_legal_marks,
            banned_dedupe_keys=banned_dedupe_keys,
        )
        values = {**asdict(card), "ingested_at": func.now()}
        await session.execute(
            insert(Card).values(**values).on_conflict_do_update(index_elements=[Card.id], set_=values)
        )

    await session.commit()
