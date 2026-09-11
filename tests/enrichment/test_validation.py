from app.clients.enrichment_client import EnrichmentResult
from app.enrichment import status
from app.enrichment.validation import validate_enrichment_result


def test_a_result_with_only_taxonomy_tags_is_completed() -> None:
    result = EnrichmentResult(
        dedupe_key="k1",
        normalized_description="Draw cards from your deck.",
        tags=["draw", "search"],
        rationale="Fetches and draws.",
    )

    validated = validate_enrichment_result(result)

    assert validated.status == status.COMPLETED
    assert validated.tags == ["draw", "search"]


def test_an_out_of_taxonomy_tag_routes_to_repair_and_is_dropped() -> None:
    result = EnrichmentResult(
        dedupe_key="k1",
        normalized_description="Draw cards from your deck.",
        tags=["draw", "not-a-real-tag"],
        rationale="Fetches and draws.",
    )

    validated = validate_enrichment_result(result)

    assert validated.status == status.NEEDS_REPAIR
    assert validated.tags == ["draw"]


def test_a_refusal_routes_to_repair_even_with_no_tags() -> None:
    result = EnrichmentResult(dedupe_key="k1")

    validated = validate_enrichment_result(result)

    assert validated.status == status.NEEDS_REPAIR
    assert validated.tags == []


def test_a_legitimately_tag_less_card_with_a_description_is_still_completed() -> None:
    result = EnrichmentResult(dedupe_key="k1", normalized_description="A vanilla attacker with no other effect.", tags=[])

    validated = validate_enrichment_result(result)

    assert validated.status == status.COMPLETED
    assert validated.tags == []
