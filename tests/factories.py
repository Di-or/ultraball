from datetime import date

from app.catalog.models import Card
from app.enrichment import status
from app.enrichment.models import CardEnrichment
from app.enrichment.taxonomy import PROMPT_VERSION, TAXONOMY_VERSION


def make_card(**overrides: object) -> Card:
    """A minimally-valid `Card` row with sensible defaults, for tests that don't ingest."""
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


def make_enrichment(**overrides: object) -> CardEnrichment:
    """A minimally-valid `CardEnrichment` row, for tests exercising tag-match retrieval."""
    base = dict(
        dedupe_key=overrides.pop("dedupe_key", "charizard-1"),
        normalized_description="",
        tags=[],
        suggested_new_tag=None,
        rationale=None,
        vector=None,
        taxonomy_version=TAXONOMY_VERSION,
        prompt_version=PROMPT_VERSION,
        status=status.COMPLETED,
        batch_id=None,
    )
    base.update(overrides)
    return CardEnrichment(**base)
