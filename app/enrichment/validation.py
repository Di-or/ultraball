from dataclasses import dataclass

from app.clients.enrichment_client import EnrichmentResult
from app.enrichment import status
from app.enrichment.taxonomy import FUNCTIONAL_TAGS


@dataclass(frozen=True)
class ValidatedEnrichment:
    """What gets stored from one result: its tags, description and routing decision.

    `normalized_description` is `None` whenever the answer is routed to repair, so an
    empty string is never stored and a failed answer never reaches the embedding pass.
    """

    tags: list[str]
    normalized_description: str | None
    status: str


def validate_enrichment_result(result: EnrichmentResult) -> ValidatedEnrichment:
    """Refusal-first: a failed answer or an out-of-taxonomy tag routes to the repair path.

    A refused, truncated or unparseable answer arrives with no description; so does one
    that is malformed in some other way. Every card has an effect to describe (a vanilla
    attacker included), so a missing description always means the answer failed, and is
    checked before the enum filter so a refusal is never mistaken for a legitimately
    tag-less card (CONTEXT.md: Enrichment identity).

    Strict Structured Outputs already constrains the model's tags at generation time,
    but this is the last line of defense before a bad tag reaches `card_enrichment` — a
    stale schema cache or provider-side bug could still slip one through. The valid
    tags are kept, so the card stays reachable through tag-match while it waits.
    """
    valid_tags = [tag for tag in result.tags if tag in FUNCTIONAL_TAGS]
    has_normalized_description = bool(result.normalized_description and result.normalized_description.strip())
    if not has_normalized_description or len(valid_tags) != len(result.tags):
        return ValidatedEnrichment(tags=valid_tags, normalized_description=None, status=status.NEEDS_REPAIR)

    return ValidatedEnrichment(
        tags=result.tags, normalized_description=result.normalized_description, status=status.COMPLETED
    )
