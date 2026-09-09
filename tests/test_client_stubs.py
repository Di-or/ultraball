from app.clients.embedding_client import EMBEDDING_DIM, EmbeddingClient
from app.clients.parse_client import ParseClient, ParseResult
from tests.stubs import StubEmbeddingClient, StubParseClient


async def test_stub_parse_client_returns_canned_result() -> None:
    canned = ParseResult(filters={"format": "standard"}, concept="acceleration", concept_rewritten="attach more Energy than the rule allows", tags=["acceleration"])
    stub: ParseClient = StubParseClient(canned)

    result = await stub.parse("energy acceleration under 130 HP")

    assert result is canned


async def test_stub_parse_client_defaults_to_empty_result() -> None:
    stub: ParseClient = StubParseClient()

    result = await stub.parse("charizard")

    assert result == ParseResult()


async def test_stub_embedding_client_returns_canned_vectors() -> None:
    stub: EmbeddingClient = StubEmbeddingClient()

    query_vector = await stub.embed_query("acceleration")
    doc_vectors = await stub.embed_documents(["card one", "card two"])

    assert len(query_vector) == EMBEDDING_DIM
    assert len(doc_vectors) == 2
    assert all(len(vector) == EMBEDDING_DIM for vector in doc_vectors)
