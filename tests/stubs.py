from app.clients.catalog_client import CatalogClient, SetSnapshot
from app.clients.embedding_client import EMBEDDING_DIM, EmbeddingClient
from app.clients.enrichment_client import EnrichmentClient, EnrichmentRequest, EnrichmentResult
from app.clients.parse_client import ParseClient, ParseResult
from app.enrichment import status


class StubParseClient(ParseClient):
    """Returns a canned ParseResult instead of calling the hosted model."""

    def __init__(self, canned: ParseResult | None = None) -> None:
        self._canned = canned or ParseResult()

    async def parse(self, query: str) -> ParseResult:
        return self._canned


class StubEmbeddingClient(EmbeddingClient):
    """Returns deterministic canned vectors instead of calling the hosted model."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self._dim = dim

    async def embed_query(self, text: str) -> list[float]:
        return [0.0] * self._dim

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self._dim for _ in texts]


class StubCatalogClient(CatalogClient):
    """Returns a canned SetSnapshot instead of crawling TCGdex."""

    def __init__(self, snapshots: dict[str, SetSnapshot]) -> None:
        self._snapshots = snapshots

    async def fetch_set(self, set_id: str) -> SetSnapshot:
        return self._snapshots[set_id]


class StubEnrichmentClient(EnrichmentClient):
    """Returns canned per-dedupe_key results instead of calling the hosted Batch model.

    Each `submit_batch` call is assigned a sequential id ("batch-1", "batch-2", ...).
    `poll_batch` reports `pending`/`failed` only for batch ids the test names in
    `pending_batch_ids`/`failed_batch_ids`, so a test can simulate an in-flight or
    broken batch and later "complete" it by omitting the id on a fresh stub.
    """

    def __init__(
        self,
        results_by_dedupe_key: dict[str, EnrichmentResult],
        *,
        pending_batch_ids: set[str] | None = None,
        failed_batch_ids: set[str] | None = None,
    ) -> None:
        self._results_by_dedupe_key = results_by_dedupe_key
        self._pending_batch_ids = pending_batch_ids or set()
        self._failed_batch_ids = failed_batch_ids or set()
        self._batches: dict[str, list[str]] = {}
        self._next_id = 1

    async def submit_batch(self, requests: list[EnrichmentRequest]) -> str:
        batch_id = f"batch-{self._next_id}"
        self._next_id += 1
        self._batches[batch_id] = [request.dedupe_key for request in requests]
        return batch_id

    async def poll_batch(self, batch_id: str) -> str:
        if batch_id in self._pending_batch_ids:
            return status.PENDING
        if batch_id in self._failed_batch_ids:
            return status.FAILED
        return status.COMPLETED

    async def fetch_results(self, batch_id: str) -> list[EnrichmentResult]:
        return [self._results_by_dedupe_key[dedupe_key] for dedupe_key in self._batches[batch_id]]
