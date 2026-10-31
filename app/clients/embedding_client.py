from abc import ABC, abstractmethod
from collections.abc import Iterator

import httpx

EMBEDDING_DIM = 1024
_VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
_VOYAGE_DOCUMENT_MODEL = "voyage-4-large"
_VOYAGE_QUERY_MODEL = "voyage-4"
_VOYAGE_MAX_TEXTS_PER_REQUEST = 1000
_VOYAGE_MAX_TOKENS_PER_REQUEST = {"voyage-4-large": 120_000, "voyage-4": 320_000}


class EmbeddingClient(ABC):
    """Seam between the request/enrichment paths and the hosted embedding model.

    Query and document embeddings are kept as separate methods because retrieval-tuned
    embedding models (the Voyage voyage-4 series) apply different instructions per side
    of the query/passage asymmetry, and because the two sides may use different models.
    """

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]: ...

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class HostedEmbeddingClient(EmbeddingClient):
    """Calls Voyage: documents with `voyage-4-large`, queries with `voyage-4`, both 1024-dim.

    Query and document embeddings use different `input_type` values on the same
    endpoint — the mechanism behind the query/passage asymmetry (CONTEXT.md).

    Mixing models is valid because the voyage-4 series share one embedding space, so a
    `voyage-4-large` card vector compares directly with a `voyage-4` query vector.
    Documents are embedded offline, where the larger model's latency doesn't matter;
    queries run while the user waits. Stored document vectors carry no model stamp, so
    changing the document model after real ingest needs the vectors cleared first.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def embed_query(self, text: str) -> list[float]:
        [vector] = await self._embed([text], model=_VOYAGE_QUERY_MODEL, input_type="query")
        return vector

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts, model=_VOYAGE_DOCUMENT_MODEL, input_type="document")

    async def _embed(self, texts: list[str], *, model: str, input_type: str) -> list[list[float]]:
        """Embeds `texts` in order, split into requests Voyage will accept."""
        vectors: list[list[float]] = []
        async with httpx.AsyncClient() as client:
            for chunk in _requests_within_limits(texts, max_tokens=_VOYAGE_MAX_TOKENS_PER_REQUEST[model]):
                response = await client.post(
                    _VOYAGE_API_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"input": chunk, "model": model, "input_type": input_type, "output_dimension": EMBEDDING_DIM},
                )
                response.raise_for_status()
                vectors.extend(item["embedding"] for item in response.json()["data"])

        return vectors


def _requests_within_limits(texts: list[str], *, max_tokens: int) -> Iterator[list[str]]:
    """Packs `texts`, in order, into runs under Voyage's per-request text and token caps.

    Voyage publishes no tokenizer we depend on, so a text's UTF-8 byte length stands in
    for its token count: a tokenizer never makes more than one token per byte, so the
    estimate only ever overshoots. A single text over the budget still goes alone, since
    Voyage truncates each input to the model's context length.
    """
    chunk: list[str] = []
    chunk_tokens = 0
    for text in texts:
        text_tokens = len(text.encode())
        if chunk and (len(chunk) == _VOYAGE_MAX_TEXTS_PER_REQUEST or chunk_tokens + text_tokens > max_tokens):
            yield chunk
            chunk, chunk_tokens = [], 0
        chunk.append(text)
        chunk_tokens += text_tokens
    if chunk:
        yield chunk
