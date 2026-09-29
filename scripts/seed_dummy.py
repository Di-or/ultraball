"""Load a small set of made-up cards into the local Postgres, for clicking through the app.

Run by hand: `uv run python -m scripts.seed_dummy`. Not part of the app.

Cards go through the real `run_ingest`, `submit_enrichment_batch`/`poll_and_apply_batch`
and `run_embedding_pass`, with canned clients in place of TCGdex and the hosted models.
Stub embeddings don't reflect what a card does, so search results look plausible but
aren't meaningful. Re-running is a no-op: ingest upserts by id, and enrichment and
embedding skip anything already done.
"""

import asyncio
import hashlib
import random
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.identity import build_card_identity
from app.catalog.ingest import run_ingest
from app.catalog.models import Base as CatalogBase
from app.clients.catalog_client import SetSnapshot
from app.clients.embedding_client import EMBEDDING_DIM, EmbeddingClient
from app.clients.enrichment_client import EnrichmentResult
from app.config import Settings
from app.db import make_engine, make_session_factory
from app.enrichment.embedding import run_embedding_pass
from app.enrichment.models import Base as EnrichmentBase
from app.enrichment.pipeline import poll_and_apply_batch, submit_enrichment_batch
from app.search.embedding_cache import Base as QueryEmbeddingCacheBase
from app.search.parse_cache import Base as ParseCacheBase
from tests.stubs import StubCatalogClient, StubEnrichmentClient


def _pokemon(
    id: str, name: str, type_: str, hp: int, rarity: str, mark: str, attack: str, effect: str, **extra: object
) -> dict:
    return dict(
        id=id,
        localId=id.split("-")[1],
        name=name,
        category="Pokemon",
        hp=hp,
        types=[type_],
        stage=extra.pop("stage", "Basic"),
        rarity=rarity,
        regulationMark=mark,
        retreat=extra.pop("retreat", 1),
        attacks=[{"name": attack, "cost": [type_, "Colorless"], "damage": 30, "effect": effect}],
        abilities=extra.pop("abilities", []),
        **extra,
    )


def _trainer(id: str, name: str, trainer_type: str, rarity: str, mark: str, effect: str) -> dict:
    return dict(
        id=id,
        localId=id.split("-")[1],
        name=name,
        category="Trainer",
        trainerType=trainer_type,
        rarity=rarity,
        regulationMark=mark,
        effect=effect,
    )


def _basic_energy(id: str, type_: str) -> dict:
    return dict(
        id=id,
        localId=id.split("-")[1],
        name=f"{type_} Energy",
        category="Energy",
        energyType="Basic",
        rarity="Common",
    )


# Newest first: dummy3 (2025) > dummy2 (2024) > dummy1 (2022). Marks H/I/J are Standard-legal,
# D/E/F/G are not (see app/catalog/legality_config.py).
SNAPSHOTS: dict[str, SetSnapshot] = {
    "dummy1": SetSnapshot(
        "dummy1",
        date(2022, 6, 1),
        [
            _pokemon("dummy1-1", "Emberling", "Fire", 60, "Common", "E", "Flare", "Flip a coin. If heads, burn the Defending Pokémon."),
            _pokemon("dummy1-2", "Flamewyrm", "Fire", 130, "Rare", "E", "Inferno Tail", "Discard an Energy from this Pokémon.", stage="Stage 1", retreat=2),
            _pokemon("dummy1-3", "Tidecaller", "Water", 90, "Uncommon", "F", "Bubble Beam", "Draw a card."),
            _pokemon("dummy1-4", "Sparkfox", "Lightning", 70, "Common", "D", "Zap", "Switch this Pokémon with 1 of your Benched Pokémon."),
            _trainer("dummy1-5", "Old Research Notes", "Supporter", "Uncommon", "E", "Draw 3 cards."),
            _trainer("dummy1-6", "Worn Ball", "Item", "Common", "D", "Search your deck for a Basic Pokémon and put it into your hand."),
            _basic_energy("dummy1-7", "Fire"),
            _basic_energy("dummy1-8", "Water"),
        ],
        official_abbreviation="DM1",
    ),
    "dummy2": SetSnapshot(
        "dummy2",
        date(2024, 3, 15),
        [
            _pokemon("dummy2-1", "Leafkit", "Grass", 70, "Common", "H", "Vine Lash", "Heal 20 damage from this Pokémon."),
            _pokemon("dummy2-2", "Verdantree ex", "Grass", 250, "Double Rare", "H", "Overgrowth", "Attach 2 basic Energy from your discard pile to your Benched Pokémon.", stage="Stage 1", retreat=3),
            _pokemon("dummy2-3", "Psychic Owl", "Psychic", 110, "Rare", "H", "Mind Bend", "Your opponent's Active Pokémon is now Confused.", abilities=[{"name": "Keen Eyes", "effect": "Look at the top 2 cards of your deck."}]),
            _pokemon("dummy2-4", "Stonehorn", "Fighting", 120, "Uncommon", "G", "Rock Toss", "This attack does 20 damage to 1 of your opponent's Benched Pokémon.", retreat=3),
            _pokemon("dummy2-5", "Dreamcat", "Psychic", 100, "Illustration Rare", "H", "Nap Time", "Heal all damage from this Pokémon. It is now Asleep.", stage="Stage 1"),
            _trainer("dummy2-6", "Switch Cart", "Item", "Common", "H", "Switch your Active Pokémon with 1 of your Benched Pokémon."),
            _trainer("dummy2-7", "Professor Birch's Lab", "Stadium", "Uncommon", "G", "Each player draws an extra card at the start of their turn."),
            _pokemon("dummy2-10", "Pixiebell", "Fairy", 80, "Uncommon", "H", "Charm Chime", "Your opponent's Active Pokémon can't retreat during their next turn."),
            _pokemon("dummy2-11", "Wyrmling", "Dragon", 100, "Rare", "H", "Dragon Pulse", "Discard 2 Energy from this Pokémon.", stage="Stage 1", retreat=2),
            _pokemon("dummy2-12", "Plainpup", "Colorless", 60, "Common", "G", "Headbutt", "Draw a card.", retreat=0),
            _basic_energy("dummy2-8", "Grass"),
            _basic_energy("dummy2-9", "Psychic"),
        ],
        official_abbreviation="DM2",
    ),
    "dummy3": SetSnapshot(
        "dummy3",
        date(2025, 9, 20),
        [
            _pokemon("dummy3-1", "Voltmouse", "Lightning", 60, "Common", "I", "Static Shock", "Discard the top card of your opponent's deck."),
            _pokemon("dummy3-2", "Thunderdrake ex", "Lightning", 280, "Ultra Rare", "I", "Storm Surge", "This attack does 30 more damage for each Energy attached to your opponent's Active Pokémon.", stage="Stage 1", retreat=3),
            _pokemon("dummy3-3", "Mega Ironclaw ex", "Metal", 330, "Hyper Rare", "I", "Steel Crush", "During your opponent's next turn, this Pokémon takes 30 less damage.", stage="Stage 2", retreat=4),
            _pokemon("dummy3-4", "Shadow Fang", "Darkness", 90, "Special Illustration Rare", "J", "Night Bite", "Your opponent discards a card from their hand.", stage="Stage 1"),
            _pokemon("dummy3-5", "Pebblet", "Fighting", 50, "Rare", "J", "Roll Out", "Search your deck for an Energy card and attach it to this Pokémon.", retreat=2),
            _trainer("dummy3-6", "Boss's Whistle", "Supporter", "Uncommon", "I", "Switch 1 of your opponent's Benched Pokémon with their Active Pokémon."),
            _trainer("dummy3-7", "Precision Sight", "Tool", "Rare", "J", "The Pokémon this card is attached to does 10 more damage to your opponent's Active Pokémon."),
            _trainer("dummy3-8", "Perfect Scope", "Item", "ACE SPEC Rare", "I", "Draw cards until you have 7 cards in your hand."),
            _basic_energy("dummy3-9", "Lightning"),
            _basic_energy("dummy3-10", "Metal"),
        ],
        official_abbreviation="DM3",
    ),
}

# Functional tags per card name (taxonomy: app/enrichment/taxonomy.py); cards not listed get none.
TAGS_BY_NAME: dict[str, list[str]] = {
    "Emberling": ["special-condition"],
    "Flamewyrm": ["energy-removal"],
    "Tidecaller": ["draw"],
    "Sparkfox": ["switch"],
    "Old Research Notes": ["draw"],
    "Worn Ball": ["search"],
    "Leafkit": ["healing"],
    "Verdantree ex": ["acceleration", "energy-recovery"],
    "Psychic Owl": ["special-condition", "search"],
    "Stonehorn": ["snipe", "spread"],
    "Dreamcat": ["healing", "special-condition"],
    "Pixiebell": ["movement-lock"],
    "Wyrmling": ["energy-removal"],
    "Plainpup": ["draw"],
    "Switch Cart": ["switch"],
    "Professor Birch's Lab": ["draw"],
    "Voltmouse": ["mill"],
    "Thunderdrake ex": ["damage-scaling"],
    "Mega Ironclaw ex": ["damage-reduction"],
    "Shadow Fang": ["hand-disruption"],
    "Pebblet": ["acceleration", "energy-search"],
    "Boss's Whistle": ["gust"],
    "Precision Sight": ["damage-scaling"],
    "Perfect Scope": ["draw"],
}


class SeedEmbeddingClient(EmbeddingClient):
    """Deterministic, text-dependent vectors, so seeded search results aren't all tied."""

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        rng = random.Random(hashlib.sha256(text.encode()).digest())
        return [rng.uniform(-1.0, 1.0) for _ in range(EMBEDDING_DIM)]


def _enrichment_results() -> dict[str, EnrichmentResult]:
    results = {}
    for snapshot in SNAPSHOTS.values():
        for raw in snapshot.cards:
            identity = build_card_identity(raw)
            results[identity.dedupe_key] = EnrichmentResult(
                dedupe_key=identity.dedupe_key,
                normalized_description=identity.canonical_card_text,
                tags=TAGS_BY_NAME.get(raw["name"], []),
            )
    return results


async def seed(session: AsyncSession) -> None:
    catalog_client = StubCatalogClient(SNAPSHOTS)
    for set_id in SNAPSHOTS:
        await run_ingest(session, catalog_client, set_id)

    enrichment_client = StubEnrichmentClient(_enrichment_results())
    batch_id = await submit_enrichment_batch(session, enrichment_client)
    if batch_id is not None:
        await poll_and_apply_batch(session, enrichment_client, batch_id)

    await run_embedding_pass(session, SeedEmbeddingClient())


async def main() -> None:
    engine = make_engine(Settings().database_url)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        for base in (CatalogBase, EnrichmentBase, ParseCacheBase, QueryEmbeddingCacheBase):
            await conn.run_sync(base.metadata.create_all)

    async with make_session_factory(engine)() as session:
        await seed(session)
    await engine.dispose()
    print(f"Seeded {len(SNAPSHOTS)} dummy sets.")


if __name__ == "__main__":
    asyncio.run(main())
