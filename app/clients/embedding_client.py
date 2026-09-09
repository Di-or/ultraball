from abc import ABC, abstractmethod

EMBEDDING_DIM = 1024


class EmbeddingClient(ABC):
    """Seam between the request/enrichment paths and the hosted embedding model.

    Query and document embeddings are kept as separate methods because retrieval-tuned
    embedding models (Voyage `voyage-4`) apply different instructions per side of the
    query/passage asymmetry.
    """

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]: ...

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class HostedEmbeddingClient(EmbeddingClient):
    """Calls the hosted embedding model (Voyage `voyage-4`, 1024-dim).

    Wiring up the actual API call is a later slice; this class exists now so the
    seam it plugs into (dependency injection, testability) is locked in.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError("Hosted embedding model integration lands in a later slice")

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Hosted embedding model integration lands in a later slice")
