"""Catalog overrides (CONTEXT.md): hand-kept fixes to individual printings' TCGdex data."""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

type CatalogOverrides = Mapping[str, Mapping[str, object]]
"""Printing id → TCGdex card-JSON field → the value the catalog uses instead."""

_OVERRIDES_FILE = Path(__file__).with_name("catalog_overrides.toml")


def load_catalog_overrides(path: Path = _OVERRIDES_FILE) -> CatalogOverrides:
    with path.open("rb") as file:
        return tomllib.load(file)


@dataclass(frozen=True)
class OverrideCheck:
    """One override whose field TCGdex now supplies, for the owner to review.

    `same`: TCGdex agrees, so the override is redundant and can be deleted.
    `differs`: TCGdex disagrees; keep the override, or delete it to let TCGdex take over.
    """

    printing_id: str
    field: str
    status: Literal["same", "differs"]
    override_value: object
    tcgdex_value: object


def apply_overrides(raw: dict, overrides: CatalogOverrides) -> dict:
    """The printing as the catalog should see it: a copy of TCGdex's JSON with its overrides
    laid over it. An override always wins; `raw` itself is left untouched."""
    return {**raw, **overrides.get(raw["id"], {})}


def check_overrides(raw: dict, overrides: CatalogOverrides) -> list[OverrideCheck]:
    """The printing's overrides whose field TCGdex now supplies, compared with TCGdex's value."""
    return [
        OverrideCheck(
            printing_id=raw["id"],
            field=field,
            status="same" if raw[field] == value else "differs",
            override_value=value,
            tcgdex_value=raw[field],
        )
        for field, value in overrides.get(raw["id"], {}).items()
        if raw.get(field) not in (None, "")
    ]
