from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SetSnapshot:
    """One set's crawl result: its release date and raw per-printing JSON."""

    set_id: str
    release_date: date
    cards: list[dict]


class CatalogClient(ABC):
    """Seam between the catalog layer and TCGdex — the only code that knows TCGdex exists."""

    @abstractmethod
    async def fetch_set(self, set_id: str) -> SetSnapshot: ...


class HostedCatalogClient(CatalogClient):
    """Crawls a set via the TCGdex SDK.

    Wiring up the actual SDK call is a later slice; this class exists now so the
    seam it plugs into (dependency injection, testability) is locked in.
    """

    async def fetch_set(self, set_id: str) -> SetSnapshot:
        raise NotImplementedError("TCGdex SDK integration lands in a later slice")
