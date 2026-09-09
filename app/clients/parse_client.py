from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParseResult:
    """The parse object: a query split into a hard filter zone and a soft concept."""

    filters: dict = field(default_factory=dict)
    concept: str = ""
    concept_rewritten: str = ""
    tags: list[str] = field(default_factory=list)


class ParseClient(ABC):
    """Seam between the request path and the hosted parse/rewrite model."""

    @abstractmethod
    async def parse(self, query: str) -> ParseResult: ...


class HostedParseClient(ParseClient):
    """Calls the hosted parse/rewrite model (GPT-5-mini, strict JSON).

    Wiring up the actual API call is a later slice; this class exists now so the
    seam it plugs into (dependency injection, testability) is locked in.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def parse(self, query: str) -> ParseResult:
        raise NotImplementedError("Hosted parse model integration lands in a later slice")
