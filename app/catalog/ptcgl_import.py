import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.deck_validation import DeckLine
from app.catalog.energy import basic_energy_type_named, is_basic_energy
from app.catalog.models import Card
from app.catalog.queries import get_basic_energy_palette, get_card_by_set_code_and_local_id

# A card line: "<count> <name...> [<set_code> <local_id>]". The set-code/local-id tail is
# optional — basic Energy is commonly listed by name alone (e.g. "8 Basic Fire Energy"),
# which is why import reads leniently rather than requiring every line to carry one
# (CONTEXT.md: Basic Energy exception; issue #28).
_LINE_RE = re.compile(r"^(?P<count>\d+)\s+(?P<rest>.+)$")
# `local_id` must contain a digit so a plain "<Type> Energy" name (no trailing set/number)
# isn't mistaken for a two-token set-code tail (e.g. "Fire Energy" is not "set=Fire, id=Energy").
# `set_code` must contain a letter but may start with a digit (`30C`) or hold a hyphen
# (`PR-SV`, the SV promos) (issue #123).
_SET_TAIL_RE = re.compile(
    r"^(?P<name>.+?)\s+(?P<set_code>(?=[A-Za-z0-9-]*[A-Za-z])[A-Za-z0-9][A-Za-z0-9-]{1,5})"
    r"\s+(?P<local_id>[A-Za-z0-9]*\d[A-Za-z0-9]*)$"
)


@dataclass(frozen=True)
class ParsedLine:
    """One decoded PTCGL line, before catalog resolution.

    `name` is the full printed card name when `set_code`/`local_id` are present, or a
    bare basic-Energy type name (e.g. "Fire Energy", "basic " prefix already stripped)
    when they're absent.
    """

    raw: str
    count: int
    name: str
    set_code: str | None
    local_id: str | None


class DeckImportError(Exception):
    """Raised when one or more PTCGL lines don't resolve to a catalog printing.

    Import is all-or-nothing on resolvability (issue #28): a single bad line fails
    the whole import rather than silently dropping it.
    """

    def __init__(self, unresolved_lines: list[str]) -> None:
        self.unresolved_lines = unresolved_lines
        super().__init__(f"{len(unresolved_lines)} line(s) did not resolve to a catalog printing")


def parse_ptcgl(text: str) -> list[ParsedLine]:
    """Decode PTCGL decklist text into card lines, skipping section headers and totals.

    Lenient by construction: any line that doesn't start with a leading count (section
    headers like "Pokémon: 12", blank lines, "Total Cards: 60") is silently skipped
    rather than treated as an error, so minor format differences don't break import.
    """
    lines: list[ParsedLine] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        match = _LINE_RE.match(stripped)
        if not match:
            continue

        count = int(match.group("count"))
        rest = match.group("rest").strip()

        tail = _SET_TAIL_RE.match(rest)
        if tail:
            lines.append(
                ParsedLine(
                    raw=stripped,
                    count=count,
                    name=tail.group("name").strip(),
                    set_code=tail.group("set_code").upper(),
                    local_id=tail.group("local_id"),
                )
            )
        else:
            name = rest
            if name.lower().startswith("basic "):
                name = name[len("basic ") :]
            lines.append(ParsedLine(raw=stripped, count=count, name=name.strip(), set_code=None, local_id=None))

    return lines


def _is_basic_energy_of_type(card: Card | None, energy_type: str) -> bool:
    return (
        card is not None
        and is_basic_energy(category=card.category, energy_type=card.energy_type)
        and basic_energy_type_named(card.name) == energy_type
    )


def _palette_match(energy_type: str, palette: list[Card]) -> Card | None:
    return next((card for card in palette if basic_energy_type_named(card.name) == energy_type), None)


async def resolve_ptcgl_import(session: AsyncSession, text: str) -> list[DeckLine]:
    """Resolve PTCGL decklist text into deck lines, all-or-nothing (issue #28).

    A line resolves against the printing its set code + local id identify. A Basic Energy line
    (`Lightning Energy MEE 12`, `Basic {R} Energy SVE 2`, `Basic Fire Energy`) keeps that exact
    printing only if it is Basic Energy of the named type; otherwise (no tail, or a tail like
    older exports' `Energy 2` that names no set, or one naming another card) it resolves against
    the fixed basic-Energy palette (issue #123). If any line fails to resolve, `DeckImportError` carries every
    failing line so the whole import can be rejected.

    Returns the resolved `Card` alongside each count (not just the printing id) so the
    caller can render the imported deck without a second round trip (issue #31).
    """
    parsed = parse_ptcgl(text)
    palette = await get_basic_energy_palette(session)

    lines: list[DeckLine] = []
    unresolved: list[str] = []

    for line in parsed:
        energy_type = basic_energy_type_named(line.name)
        card = None
        if line.set_code and line.local_id:
            card = await get_card_by_set_code_and_local_id(session, line.set_code, line.local_id, name=line.name)
        if energy_type is not None and not _is_basic_energy_of_type(card, energy_type):
            card = _palette_match(energy_type, palette)

        if card is None:
            unresolved.append(line.raw)
        else:
            lines.append(DeckLine(card=card, count=line.count))

    if unresolved:
        raise DeckImportError(unresolved)

    return lines
