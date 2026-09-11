from dataclasses import dataclass

from app.clients.enrichment_client import EnrichmentResult
from app.enrichment import status
from app.enrichment.taxonomy import FUNCTIONAL_TAGS


@dataclass(frozen=True)
class ValidatedEnrichment:
    """The tags and routing decision produced by running a result through the validator."""

    tags: list[str]
    status: str


def validate_enrichment_result(result: EnrichmentResult) -> ValidatedEnrichment:
    """Refusal-first: a refusal or an out-of-taxonomy tag routes to the repair path.

    Strict Structured Outputs already constrains the model's choices at generation
    time, but this is the last line of defense before a bad tag reaches
    `card_enrichment` — a stale schema cache or provider-side bug could still slip
    one through. Checked before the enum filter so a refusal is never mistaken for
    a legitimately tag-less card (CONTEXT.md: Enrichment identity).
    """
    is_refusal = not result.normalized_description and not result.tags and not result.suggested_new_tag
    if is_refusal:
        return ValidatedEnrichment(tags=[], status=status.NEEDS_REPAIR)

    valid_tags = [tag for tag in result.tags if tag in FUNCTIONAL_TAGS]
    if len(valid_tags) != len(result.tags):
        return ValidatedEnrichment(tags=valid_tags, status=status.NEEDS_REPAIR)

    return ValidatedEnrichment(tags=result.tags, status=status.COMPLETED)
