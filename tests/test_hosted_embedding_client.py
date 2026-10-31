import json

import httpx
import pytest

from app.clients import embedding_client
from app.clients.embedding_client import HostedEmbeddingClient


@pytest.fixture
def sent_requests(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    """Answers each hosted embedding call with one vector per input, recording what was sent.

    Each vector is `[n]` for an input text `"card n"`, so the caller can check that
    vectors come back in the same order as the texts went in.
    """
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        texts = json.loads(request.content)["input"]
        data = [{"embedding": [float(text.split()[1])], "index": i} for i, text in enumerate(texts)]
        return httpx.Response(200, json={"data": data})

    real_async_client = httpx.AsyncClient

    def mocked_async_client(**kwargs: object) -> httpx.AsyncClient:
        return real_async_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(embedding_client.httpx, "AsyncClient", mocked_async_client)
    return requests


async def test_hosted_embed_documents_splits_into_requests_of_at_most_1000_texts(
    sent_requests: list[httpx.Request],
) -> None:
    # Voyage rejects a request with more than 1,000 texts, and the embedding pass sends
    # every pending description at once — a few thousand on a first run.
    texts = [f"card {n}" for n in range(2500)]

    vectors = await HostedEmbeddingClient(api_key="test-key").embed_documents(texts)

    batch_sizes = [len(json.loads(request.content)["input"]) for request in sent_requests]
    assert batch_sizes == [1000, 1000, 500]
    assert vectors == [[float(n)] for n in range(2500)]
