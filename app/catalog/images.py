from collections.abc import Iterable
from posixpath import splitext
from typing import Literal
from urllib.parse import urlsplit

from app.catalog.models import Card

_TCGDEX_ASSETS_HOST = "assets.tcgdex.net"

type ImageSize = Literal["high", "low"]
"""TCGdex's two renditions: `high` for the card-detail view, `low` for small tiles."""


def image_url(image: str | None, size: ImageSize) -> str | None:
    """A printing's stored `image` as a URL a browser can load.

    TCGdex stores a base URL (`https://assets.tcgdex.net/en/sv/svp/150`) that needs a rendition
    appended (`/high.webp`). Any other URL, such as art from elsewhere set by a catalog override,
    is already a complete image and is used as is, at every size.
    """
    if not image:
        return None
    parts = urlsplit(image)
    if parts.hostname == _TCGDEX_ASSETS_HOST and not splitext(parts.path)[1]:
        return f"{image.rstrip('/')}/{size}.webp"
    return image


def entity_image_url(printings: Iterable[Card], size: ImageSize) -> str | None:
    """The art for a card entity: its representative printing's, or, when that has none, the
    next printing's that does (CONTEXT.md: Representative printing). Every printing of an entity
    has the same text, so any of them shows the right card.

    `printings` is in representative order (`representative_order`).
    """
    return next((url for card in printings if (url := image_url(card.image, size))), None)
