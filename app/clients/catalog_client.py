import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime

import httpx

_TCGDEX_LANGUAGE = "en"
_TCGDEX_API_URL = f"https://api.tcgdex.net/v2/{_TCGDEX_LANGUAGE}"
_TCGDEX_ASSETS_URL = f"https://assets.tcgdex.net/{_TCGDEX_LANGUAGE}"
_ATTEMPTS = 4
_TIMEOUT_SECONDS = 30
_MAX_RETRY_AFTER_SECONDS = 60.0
_IMAGE_CHECK_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class SetSnapshot:
    """One set's crawl result: its name, release date and raw per-printing JSON."""

    set_id: str
    release_date: date
    cards: list[dict]
    official_abbreviation: str | None = None
    """`set.abbreviation.official` from TCGdex, the input to PTCGL set-code derivation
    (CONTEXT.md: catalog layer; issue #28)."""
    name: str = ""
    """The TCGdex set name (e.g. "Twilight Masquerade"), which the parse model resolves a
    named set against (issue #90)."""


class CatalogClient(ABC):
    """Seam between the catalog layer and TCGdex — the only code that knows TCGdex exists."""

    @abstractmethod
    async def fetch_set(self, set_id: str) -> SetSnapshot: ...


class HostedCatalogClient(CatalogClient):
    """Crawls a set from the TCGdex REST API: the set, then each of its printings' full JSON."""

    def __init__(self, *, max_concurrent_requests: int = 4, retry_delay_seconds: float = 1.0) -> None:
        self._max_concurrent_requests = max_concurrent_requests
        self._retry_delay_seconds = retry_delay_seconds

    async def fetch_set(self, set_id: str) -> SetSnapshot:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            set_json = await self._get_json(client, f"sets/{set_id}")
            assets_url = f"{_TCGDEX_ASSETS_URL}/{set_json['serie']['id']}/{set_json['id']}"
            cards = await self._get_cards(client, [card["id"] for card in set_json["cards"]], assets_url)

        return SetSnapshot(
            set_id=set_json["id"],
            release_date=date.fromisoformat(set_json["releaseDate"]),
            cards=cards,
            official_abbreviation=(set_json.get("abbreviation") or {}).get("official"),
            name=set_json["name"],
        )

    async def _get_cards(self, client: httpx.AsyncClient, printing_ids: list[str], assets_url: str) -> list[dict]:
        """Each printing's full JSON, in the order given, a bounded number in flight at once.

        Uncached requests reach TCGdex's origin, which answers 503 under load, so the
        crawl stays gentle. If any card fails, the rest are cancelled and its error raised.

        A printing whose JSON lists no `image` gets one if its art is on TCGdex's image
        server at the usual address under `assets_url`: the API's metadata lags the image
        server (issue #145).
        """
        semaphore = asyncio.Semaphore(self._max_concurrent_requests)

        async def get_card(printing_id: str) -> dict:
            async with semaphore:
                card = await self._get_json(client, f"cards/{printing_id}")
                if not card.get("image"):
                    image = f"{assets_url}/{card['localId']}"
                    if await _has_art(client, image):
                        card["image"] = image
                return card

        try:
            async with asyncio.TaskGroup() as task_group:
                tasks = [task_group.create_task(get_card(printing_id)) for printing_id in printing_ids]
        except ExceptionGroup as group:
            raise group.exceptions[0]
        return [task.result() for task in tasks]

    async def _get_json(self, client: httpx.AsyncClient, path: str) -> dict:
        """GETs one TCGdex resource, retrying transient failures with exponential backoff.

        A failure that outlasts the retries, or isn't transient (e.g. a 404), is raised.
        """
        for attempt in range(_ATTEMPTS):
            last_attempt = attempt == _ATTEMPTS - 1
            wait_seconds = self._retry_delay_seconds * 2**attempt
            try:
                # TCGdex's CDN can serve a copy that is weeks old, so every request asks
                # for no cache and carries a query value no other request used
                # (research/pre-tagging-pipeline-check.md, 2026-11-08 corrections).
                response = await client.get(
                    f"{_TCGDEX_API_URL}/{path}",
                    params={"cb": uuid.uuid4().hex},
                    headers={"Cache-Control": "no-cache"},
                )
            except httpx.TransportError:
                if last_attempt:
                    raise
            else:
                if not _is_transient(response) or last_attempt:
                    response.raise_for_status()
                    return response.json()
                if (asked_seconds := _retry_after_seconds(response)) is not None:
                    wait_seconds = asked_seconds
            await asyncio.sleep(wait_seconds)
        raise AssertionError("unreachable")


async def _has_art(client: httpx.AsyncClient, image: str) -> bool:
    """Whether TCGdex's image server has art at the base URL `image`, judged by its small
    rendition. A check that fails or times out counts as no art, so the printing ingests
    without an image and a later ingest tries again."""
    try:
        response = await client.head(f"{image}/low.webp", timeout=_IMAGE_CHECK_TIMEOUT_SECONDS)
    except httpx.HTTPError:
        return False
    return response.is_success


def _is_transient(response: httpx.Response) -> bool:
    return response.status_code == 429 or response.is_server_error


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """How long the server asked us to wait, capped; None if it didn't say in a usable way.

    `Retry-After` is either a number of seconds or an HTTP date. The cap stops one odd
    header from stalling the whole ingest.
    """
    header = response.headers.get("Retry-After")
    if header is None:
        return None
    try:
        seconds = float(header)
    except ValueError:
        try:
            seconds = (parsedate_to_datetime(header) - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError):
            return None
    return min(max(seconds, 0.0), _MAX_RETRY_AFTER_SECONDS)
