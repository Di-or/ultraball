import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

import httpx
import pytest

from app.clients import catalog_client
from app.clients.catalog_client import HostedCatalogClient
from tests.tcgdex_fixtures import FIXTURE_PRINTING_IDS, load_printing, load_set


def _serve_fixtures(request: httpx.Request) -> httpx.Response:
    """Answers like TCGdex from the committed fixtures.

    A set's card list is cut down to the printings committed for it, since only those have
    card JSON to serve.
    """
    kind, _, item_id = request.url.path.removeprefix("/v2/en/").partition("/")
    if kind == "sets":
        set_json = load_set(item_id)
        set_json["cards"] = [card for card in set_json["cards"] if card["id"] in FIXTURE_PRINTING_IDS]
        return httpx.Response(200, json=set_json)
    if kind == "cards" and item_id in FIXTURE_PRINTING_IDS:
        return httpx.Response(200, json=load_printing(item_id))
    return httpx.Response(404)


class MockTcgdex:
    """Stands in for TCGdex: answers each request with `handler`, recording it in `requests`.

    `handler` answers from the committed fixtures until a test swaps it.
    """

    def __init__(self) -> None:
        self.handler: Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]] = _serve_fixtures
        self.requests: list[httpx.Request] = []

    async def dispatch(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        response = self.handler(request)
        if not isinstance(response, httpx.Response):
            response = await response
        return response


@pytest.fixture
def mock_tcgdex(monkeypatch: pytest.MonkeyPatch) -> MockTcgdex:
    """Routes the hosted catalog client's HTTP calls to a `MockTcgdex`."""
    mock = MockTcgdex()
    real_async_client = httpx.AsyncClient

    def mocked_async_client(**kwargs: Any) -> httpx.AsyncClient:
        return real_async_client(transport=httpx.MockTransport(mock.dispatch), **kwargs)

    monkeypatch.setattr(catalog_client.httpx, "AsyncClient", mocked_async_client)
    return mock


def _synthetic_set(card_count: int) -> dict:
    return {
        "id": "big",
        "name": "Big Set",
        "releaseDate": "2026-01-01",
        "cards": [{"id": f"big-{n:03}", "localId": f"{n:03}", "name": f"Card {n}"} for n in range(card_count)],
    }


def _is_set_request(request: httpx.Request) -> bool:
    return request.url.path.startswith("/v2/en/sets/")


def _card_number(request: httpx.Request) -> int:
    return int(request.url.path.rsplit("-", 1)[1])


def _echo_card(request: httpx.Request) -> httpx.Response:
    """A minimal printing JSON for the requested card: just its id."""
    return httpx.Response(200, json={"id": request.url.path.rsplit("/", 1)[1]})


async def test_hosted_fetch_set_builds_a_snapshot_from_the_set_and_each_printings_full_json(
    mock_tcgdex: MockTcgdex,
) -> None:
    snapshot = await HostedCatalogClient(retry_delay_seconds=0).fetch_set("mep")

    assert snapshot.set_id == "mep"
    assert snapshot.name == "MEP Black Star Promos"
    assert snapshot.release_date == date(2025, 9, 26)
    assert snapshot.official_abbreviation == "MEP"
    assert [card["id"] for card in snapshot.cards] == ["mep-023", "mep-051"]
    assert snapshot.cards == [load_printing("mep-023"), load_printing("mep-051")]


async def test_hosted_fetch_set_bypasses_the_cdn_cache_on_every_request(mock_tcgdex: MockTcgdex) -> None:
    # TCGdex's CDN can serve a copy that is weeks old (research/pre-tagging-pipeline-check.md,
    # 2026-11-08 corrections), so each request asks for no cache and carries a query value
    # no earlier request used.
    await HostedCatalogClient(retry_delay_seconds=0).fetch_set("mep")

    assert len(mock_tcgdex.requests) == 3
    assert all(request.headers.get("Cache-Control") == "no-cache" for request in mock_tcgdex.requests)
    cache_busters = [request.url.params.get("cb") for request in mock_tcgdex.requests]
    assert None not in cache_busters
    assert len(set(cache_busters)) == len(cache_busters)


async def test_hosted_fetch_set_fetches_cards_concurrently_up_to_the_limit_and_keeps_set_order(
    mock_tcgdex: MockTcgdex,
) -> None:
    in_flight = 0
    peak_in_flight = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak_in_flight
        if _is_set_request(request):
            return httpx.Response(200, json=_synthetic_set(20))
        in_flight += 1
        peak_in_flight = max(peak_in_flight, in_flight)
        # Later cards answer sooner, so a client that kept responses in arrival order
        # would get the set order wrong.
        await asyncio.sleep(0.001 * (20 - _card_number(request)))
        in_flight -= 1
        return _echo_card(request)

    mock_tcgdex.handler = handler

    snapshot = await HostedCatalogClient(max_concurrent_requests=4, retry_delay_seconds=0).fetch_set("big")

    assert peak_in_flight == 4
    assert [card["id"] for card in snapshot.cards] == [f"big-{n:03}" for n in range(20)]


async def test_hosted_fetch_set_retries_transient_failures(mock_tcgdex: MockTcgdex) -> None:
    # Uncached requests reach TCGdex's origin, which answers 503 under load.
    first_answers: dict[str, list[httpx.Response | Exception]] = {
        "/v2/en/sets/big": [httpx.Response(503)],
        "/v2/en/cards/big-000": [httpx.Response(503), httpx.Response(503)],
        "/v2/en/cards/big-001": [httpx.Response(429)],
        "/v2/en/cards/big-002": [httpx.ConnectError("connection reset")],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        queued = first_answers.get(request.url.path, [])
        if queued:
            answer = queued.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer
        if _is_set_request(request):
            return httpx.Response(200, json=_synthetic_set(3))
        return _echo_card(request)

    mock_tcgdex.handler = handler

    snapshot = await HostedCatalogClient(retry_delay_seconds=0).fetch_set("big")

    assert snapshot.name == "Big Set"
    assert [card["id"] for card in snapshot.cards] == ["big-000", "big-001", "big-002"]


async def test_hosted_fetch_set_raises_when_a_card_keeps_failing_rather_than_dropping_it(
    mock_tcgdex: MockTcgdex,
) -> None:
    # A snapshot missing a card would ingest as a set without it, silently.
    def handler(request: httpx.Request) -> httpx.Response:
        if _is_set_request(request):
            return httpx.Response(200, json=_synthetic_set(3))
        if _card_number(request) == 1:
            return httpx.Response(503)
        return _echo_card(request)

    mock_tcgdex.handler = handler

    with pytest.raises(httpx.HTTPStatusError) as raised:
        await HostedCatalogClient(retry_delay_seconds=0).fetch_set("big")

    assert raised.value.response.status_code == 503
    assert raised.value.request.url.path == "/v2/en/cards/big-001"
    assert sum(request.url.path == "/v2/en/cards/big-001" for request in mock_tcgdex.requests) == 4


async def test_hosted_fetch_set_raises_a_missing_card_without_retrying(mock_tcgdex: MockTcgdex) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if _is_set_request(request):
            return httpx.Response(200, json=_synthetic_set(1))
        return httpx.Response(404)

    mock_tcgdex.handler = handler

    with pytest.raises(httpx.HTTPStatusError) as raised:
        await HostedCatalogClient(retry_delay_seconds=0).fetch_set("big")

    assert raised.value.response.status_code == 404
    assert len(mock_tcgdex.requests) == 2
