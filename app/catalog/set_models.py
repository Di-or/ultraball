from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel


class SetSummary(BaseModel):
    """One distinct set, derived from the cards table (there is no sets table)."""

    id: str
    code: str
    name: str
    release_date: date


@dataclass(frozen=True)
class CatalogSet:
    """One entry of the set list the parse model resolves a named set against (issue #90)."""

    id: str
    code: str
    name: str


def render_set_lines(sets: Iterable[CatalogSet]) -> str:
    """One `id — code — name` line per set, sorted by id so the same sets always render the same.

    Both the parse system prompt and the parse cache key are built from this text,
    so the prompt the model saw and the key its answer is cached under can't drift.
    """
    return "\n".join(f"{s.id} — {s.code} — {s.name}" for s in sorted(sets, key=lambda s: s.id))
