import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

import httpx
import pytest

from app.clients import catalog_client
from app.clients.catalog_client import HostedCatalogClient
from tests.tcgdex_fixtures import FIXTURE_PRINTING_IDS, load_printing, load_set

# The `mep` printings committed as fixtures, in set order: the ones the mock serves.
_MEP_PRINTING_IDS = [printing_id for printing_id in FIXTURE_PRINTING_IDS if printing_id.startswith("mep-")]


_ASSETS_HOST = "assets.tcgdex.net"


def _serve_fixtures(request: httpx.Request) -> httpx.Response:
    """Answers like TCGdex from the committed fixtures.

    A set's card list is cut down to the printings committed for it, since only those have
    card JSON to serve. The image server has no art until a test gives it some.
    """
    if request.url.host == _ASSETS_HOST:
        return httpx.Response(404)
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
        "serie": {"id": "bg", "name": "Big Series"},
        "cards": [{"id": f"big-{n:03}", "localId": f"{n:03}", "name": f"Card {n}"} for n in range(card_count)],
    }


def _is_set_request(request: httpx.Request) -> bool:
    return request.url.path.startswith("/v2/en/sets/")


def _card_number(request: httpx.Request) -> int:
    return int(request.url.path.rsplit("-", 1)[1])


def _echo_card(request: httpx.Request) -> httpx.Response:
    """A minimal printing JSON for the requested card: its id, number and art, so the client
    has no reason to check the image server."""
    printing_id = request.url.path.rsplit("/", 1)[1]
    local_id = printing_id.rsplit("-", 1)[1]
    return httpx.Response(
        200,
        json={"id": printing_id, "localId": local_id, "image": f"https://assets.tcgdex.net/en/bg/big/{local_id}"},
    )


async def test_hosted_fetch_set_builds_a_snapshot_from_the_set_and_each_printings_full_json(
    mock_tcgdex: MockTcgdex,
) -> None:
    snapshot = await HostedCatalogClient(retry_delay_seconds=0).fetch_set("mep")

    assert snapshot.set_id == "mep"
    assert snapshot.name == "MEP Black Star Promos"
    assert snapshot.release_date == date(2025, 9, 26)
    assert snapshot.official_abbreviation == "MEP"
    assert [card["id"] for card in snapshot.cards] == _MEP_PRINTING_IDS
    assert snapshot.cards == [load_printing(printing_id) for printing_id in _MEP_PRINTING_IDS]


async def test_hosted_fetch_set_bypasses_the_cdn_cache_on_every_request(mock_tcgdex: MockTcgdex) -> None:
    # TCGdex's CDN can serve a copy that is weeks old (research/pre-tagging-pipeline-check.md,
    # 2026-11-08 corrections), so each request asks for no cache and carries a query value
    # no earlier request used.
    await HostedCatalogClient(retry_delay_seconds=0).fetch_set("mep")

    api_requests = [request for request in mock_tcgdex.requests if request.url.host != _ASSETS_HOST]
    assert len(api_requests) == 1 + len(_MEP_PRINTING_IDS)  # the set, then each committed printing
    assert all(request.headers.get("Cache-Control") == "no-cache" for request in api_requests)
    cache_busters = [request.url.params.get("cb") for request in api_requests]
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


@pytest.mark.parametrize(
    ("retry_after", "expected_wait_seconds"),
    [("7", 7.0), ("3600", 60.0), ("soon", 1.0)],
    ids=["follows-retry-after", "caps-a-long-retry-after", "ignores-an-unreadable-retry-after"],
)
async def test_hosted_fetch_set_waits_as_long_as_tcgdex_asks_before_retrying(
    mock_tcgdex: MockTcgdex,
    monkeypatch: pytest.MonkeyPatch,
    retry_after: str,
    expected_wait_seconds: float,
) -> None:
    # A server that says when to come back gets that wait, capped so one odd header can't
    # stall the ingest; without a usable one, the normal backoff applies.
    waits: list[float] = []

    async def record_wait(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(catalog_client.asyncio, "sleep", record_wait)
    first_answers = [httpx.Response(429, headers={"Retry-After": retry_after})]

    def handler(request: httpx.Request) -> httpx.Response:
        if _is_set_request(request):
            return httpx.Response(200, json=_synthetic_set(1))
        if first_answers:
            return first_answers.pop(0)
        return _echo_card(request)

    mock_tcgdex.handler = handler

    await HostedCatalogClient(retry_delay_seconds=1.0).fetch_set("big")

    assert waits == [expected_wait_seconds]


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


def _image_server_with_art(*base_paths: str) -> Callable[[httpx.Request], httpx.Response]:
    """The fixtures' TCGdex, with art on the image server at each of `base_paths`
    (e.g. `/en/sv/svp/224`). It answers a request for any rendition of that art."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == _ASSETS_HOST:
            base_path, _, rendition = request.url.path.rpartition("/")
            if base_path in base_paths and rendition in {"low.webp", "high.webp"}:
                return httpx.Response(200, headers={"Content-Type": "image/webp"})
            return httpx.Response(404)
        return _serve_fixtures(request)

    return handler


async def test_hosted_fetch_set_finds_art_the_api_does_not_list_on_the_image_server(mock_tcgdex: MockTcgdex) -> None:
    # TCGdex's API lags its image server: on 2026-11-12, svp-202 and svp-224 had art at the
    # usual address but no `image` in their JSON (issue #145).
    mock_tcgdex.handler = _image_server_with_art("/en/sv/svp/202", "/en/sv/svp/224")

    snapshot = await HostedCatalogClient(retry_delay_seconds=0).fetch_set("svp")

    images = {card["id"]: card.get("image") for card in snapshot.cards}
    assert images["svp-202"] == "https://assets.tcgdex.net/en/sv/svp/202"
    assert images["svp-224"] == "https://assets.tcgdex.net/en/sv/svp/224"


async def test_hosted_fetch_set_leaves_a_printing_with_no_art_anywhere_without_an_image(
    mock_tcgdex: MockTcgdex,
) -> None:
    mock_tcgdex.handler = _image_server_with_art("/en/sv/svp/224")

    snapshot = await HostedCatalogClient(retry_delay_seconds=0).fetch_set("svp")

    svp_190 = next(card for card in snapshot.cards if card["id"] == "svp-190")
    assert svp_190.get("image") is None


async def test_hosted_fetch_set_only_checks_the_image_server_for_printings_the_api_lists_no_image_for(
    mock_tcgdex: MockTcgdex,
) -> None:
    await HostedCatalogClient(retry_delay_seconds=0).fetch_set("svp")

    checked = sorted(request.url.path for request in mock_tcgdex.requests if request.url.host == _ASSETS_HOST)
    svp_printings = [card for card in map(load_printing, FIXTURE_PRINTING_IDS) if card["set"]["id"] == "svp"]
    expected = sorted(
        f"/en/sv/svp/{card['localId']}/low.webp" for card in svp_printings if not card.get("image")
    )
    assert expected  # the svp fixtures include printings without an image
    assert checked == expected
    assert all(request.method == "HEAD" for request in mock_tcgdex.requests if request.url.host == _ASSETS_HOST)


@pytest.mark.parametrize(
    "failure",
    [httpx.Response(503), httpx.ReadTimeout("timed out"), httpx.ConnectError("connection reset")],
    ids=["server-error", "timeout", "connection-error"],
)
async def test_hosted_fetch_set_counts_a_failed_image_check_as_no_art_without_failing(
    mock_tcgdex: MockTcgdex, failure: httpx.Response | Exception
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == _ASSETS_HOST:
            if isinstance(failure, Exception):
                raise failure
            return failure
        return _serve_fixtures(request)

    mock_tcgdex.handler = handler

    snapshot = await HostedCatalogClient(retry_delay_seconds=0).fetch_set("svp")

    images = {card["id"]: card.get("image") for card in snapshot.cards}
    assert images["svp-224"] is None
    assert images["svp-101"] == "https://assets.tcgdex.net/en/sv/svp/101"
