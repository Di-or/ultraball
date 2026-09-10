from app.clients.catalog_client import CatalogClient, SetSnapshot
from app.clients.embedding_client import EMBEDDING_DIM, EmbeddingClient
from app.clients.parse_client import ParseClient, ParseResult


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
