from datetime import datetime

from sqlalchemy import ARRAY, DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CardEnrichment(Base):
    """Per-unique-text enrichment state, keyed by dedupe_key (CONTEXT.md: card_enrichment).

    Separate from `cards` because enrichment runs once per unique text while
    `cards` is once per printing — genuine reprints share one row here.
    """

    __tablename__ = "card_enrichment"

    dedupe_key: Mapped[str] = mapped_column(String, primary_key=True)

    normalized_description: Mapped[str | None] = mapped_column(String)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    suggested_new_tag: Mapped[str | None] = mapped_column(String)
    rationale: Mapped[str | None] = mapped_column(String)

    taxonomy_version: Mapped[str] = mapped_column(String, index=True)
    prompt_version: Mapped[str] = mapped_column(String, index=True)

    status: Mapped[str] = mapped_column(String, index=True)
    batch_id: Mapped[str | None] = mapped_column(String, index=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
