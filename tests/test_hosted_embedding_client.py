import json
from typing import Any

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

    def mocked_async_client(**kwargs: Any) -> httpx.AsyncClient:
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


async def test_hosted_embed_documents_uses_voyage_4_large_and_embed_query_uses_voyage_4(
    sent_requests: list[httpx.Request],
) -> None:
    # Documents are embedded offline, so they get the larger model; queries run while the
    # user waits, so they stay on the faster one. Both stay 1024-dim to share the column.
    client = HostedEmbeddingClient(api_key="test-key")

    await client.embed_documents(["card 1"])
    await client.embed_query("card 2")

    [document_body, query_body] = [json.loads(request.content) for request in sent_requests]
    assert (document_body["model"], document_body["input_type"], document_body["output_dimension"]) == (
        "voyage-4-large",
        "document",
        1024,
    )
    assert (query_body["model"], query_body["input_type"], query_body["output_dimension"]) == ("voyage-4", "query", 1024)


async def test_hosted_embed_documents_keeps_each_request_inside_voyage_4_large_token_limit(
    sent_requests: list[httpx.Request],
) -> None:
    # voyage-4-large caps a request at 120K tokens, so 1,000 long descriptions would be
    # rejected. A text never has more tokens than UTF-8 bytes, so 1,000-byte texts fit
    # 120 to a request.
    texts = [f"card {n} ".ljust(1000, "x") for n in range(300)]

    vectors = await HostedEmbeddingClient(api_key="test-key").embed_documents(texts)

    batch_sizes = [len(json.loads(request.content)["input"]) for request in sent_requests]
    assert batch_sizes == [120, 120, 60]
    assert vectors == [[float(n)] for n in range(300)]
