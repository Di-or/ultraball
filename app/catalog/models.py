from datetime import date, datetime

from sqlalchemy import ARRAY, Boolean, Date, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawCard(Base):
    """One raw TCGdex printing snapshot, keyed by TCGdex printing id."""

    __tablename__ = "raw_cards"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    set_id: Mapped[str] = mapped_column(String, index=True)
    raw: Mapped[dict] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Card(Base):
    """One typed printing, projected from `raw_cards` (CONTEXT.md: catalog layer)."""

    __tablename__ = "cards"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    set_id: Mapped[str] = mapped_column(String, index=True)
    local_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String, index=True)
    category: Mapped[str] = mapped_column(String, index=True)

    hp: Mapped[int | None] = mapped_column(Integer)
    types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    stage: Mapped[str | None] = mapped_column(String)
    evolve_from: Mapped[str | None] = mapped_column(String)
    retreat: Mapped[int | None] = mapped_column(Integer)
    regulation_mark: Mapped[str | None] = mapped_column(String, index=True)
    rarity: Mapped[str | None] = mapped_column(String)
    trainer_type: Mapped[str | None] = mapped_column(String)
    energy_type: Mapped[str | None] = mapped_column(String)

    attacks: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    abilities: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    attack_costs: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    sub_category: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    dedupe_key: Mapped[str] = mapped_column(String, index=True)
    canonical_card_text: Mapped[str] = mapped_column(String)
    is_standard_legal: Mapped[bool] = mapped_column(Boolean, index=True)
    release_date: Mapped[date] = mapped_column(Date)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
