from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EnrichmentRequest:
    """One dedupe_key's canonical_card_text queued for a Batch enrichment call."""

    dedupe_key: str
    canonical_card_text: str


@dataclass(frozen=True)
class EnrichmentResult:
    """One dedupe_key's tagged, described output from a Batch enrichment call."""

    dedupe_key: str
    normalized_description: str = ""
    tags: list[str] = field(default_factory=list)
    suggested_new_tag: str | None = None
    rationale: str = ""


class EnrichmentClient(ABC):
    """Seam between the enrichment pipeline and the hosted Batch model.

    Submit/poll/fetch instead of one blocking call because Batch runs are
    long-lived and must be resumable: a mid-run crash resumes by polling the
    stored `batch_id` rather than resubmitting the whole corpus
    (CONTEXT.md: Enrichment identity).
    """

    @abstractmethod
    async def submit_batch(self, requests: list[EnrichmentRequest]) -> str: ...

    @abstractmethod
    async def poll_batch(self, batch_id: str) -> str: ...

    @abstractmethod
    async def fetch_results(self, batch_id: str) -> list[EnrichmentResult]: ...


class HostedEnrichmentClient(EnrichmentClient):
    """Calls the hosted Batch model (GPT-4.1-mini, temp 0, strict Structured Outputs).

    Wiring up the actual API call is a later slice; this class exists now so the
    seam it plugs into (dependency injection, testability) is locked in.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def submit_batch(self, requests: list[EnrichmentRequest]) -> str:
        raise NotImplementedError("Hosted Batch model integration lands in a later slice")

    async def poll_batch(self, batch_id: str) -> str:
        raise NotImplementedError("Hosted Batch model integration lands in a later slice")

    async def fetch_results(self, batch_id: str) -> list[EnrichmentResult]:
        raise NotImplementedError("Hosted Batch model integration lands in a later slice")
