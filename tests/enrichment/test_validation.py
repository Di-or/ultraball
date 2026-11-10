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


def test_a_refusal_stores_no_description() -> None:
    validated = validate_enrichment_result(EnrichmentResult(dedupe_key="k1"))

    assert validated.normalized_description is None


def test_tags_with_a_blank_description_route_to_repair_with_no_description() -> None:
    result = EnrichmentResult(dedupe_key="k1", normalized_description="   ", tags=["draw"], rationale="Draws.")

    validated = validate_enrichment_result(result)

    assert validated.status == status.NEEDS_REPAIR
    assert validated.normalized_description is None
    assert validated.tags == ["draw"]


def test_an_out_of_taxonomy_answer_stores_no_description() -> None:
    result = EnrichmentResult(
        dedupe_key="k1", normalized_description="Draw cards from your deck.", tags=["draw", "not-a-real-tag"]
    )

    validated = validate_enrichment_result(result)

    assert validated.normalized_description is None


def test_a_completed_answer_keeps_its_description() -> None:
    result = EnrichmentResult(dedupe_key="k1", normalized_description="Draw cards from your deck.", tags=["draw"])

    validated = validate_enrichment_result(result)

    assert validated.normalized_description == "Draw cards from your deck."
