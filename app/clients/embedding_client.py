from abc import ABC, abstractmethod

import httpx

EMBEDDING_DIM = 1024
_VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
_VOYAGE_MODEL = "voyage-4"
_VOYAGE_MAX_TEXTS_PER_REQUEST = 1000


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

    Query and document embeddings use different `input_type` values on the same
    endpoint — the mechanism behind the query/passage asymmetry (CONTEXT.md).
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def embed_query(self, text: str) -> list[float]:
        [vector] = await self._embed([text], input_type="query")
        return vector

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts, input_type="document")

    async def _embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        """Embeds `texts` in order, split into requests Voyage will accept.

        Voyage caps a request at 1,000 texts (and 320K tokens, which 1,000 short
        normalized descriptions stay well under).
        """
        vectors: list[list[float]] = []
        async with httpx.AsyncClient() as client:
            for start in range(0, len(texts), _VOYAGE_MAX_TEXTS_PER_REQUEST):
                chunk = texts[start : start + _VOYAGE_MAX_TEXTS_PER_REQUEST]
                response = await client.post(
                    _VOYAGE_API_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"input": chunk, "model": _VOYAGE_MODEL, "input_type": input_type, "output_dimension": EMBEDDING_DIM},
                )
                response.raise_for_status()
                vectors.extend(item["embedding"] for item in response.json()["data"])

        return vectors
