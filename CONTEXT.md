# Ultraball

A conceptual-search Pokémon TCG deckbuilder: describe what a card *does* in natural language and get matching, Standard-legal cards back. This glossary fixes the language the design and code share.

## Language

### Catalog

**Printing**:
A single physical publication of a card in one set — the unit TCGdex returns, identified by its set + number (e.g. `swsh1-178`). The same card reprinted in another set is a *different* printing with its own rarity, art, images, and regulation mark.
_Avoid_: card (when precision matters), variant.

**Card entity**:
The logical card shared across its printings — reprints that play identically collapse to one entity. Enrichment (tags + embedding) and the 4-copy deck rule operate on the entity, not the printing, so identical reprints are tagged once and counted together.
_Avoid_: unique card, oracle card.

**Catalog layer**:
The abstraction that isolates the rest of the app from TCGdex's shape — the only code that knows TCGdex exists. It ingests printings, keeps a raw snapshot, and projects them into the app's own schema.
_Avoid_: data layer, TCGdex client, importer.

**Errata reconciliation list**:
A curated mapping that unifies printings whose *text* diverges but which the game treats as one card (mostly Trainers corrected by official errata), so they resolve to a single card entity rather than being mistaken for distinct cards.
_Avoid_: errata table, corrections.

### Legality

**Regulation mark**:
The letter stamped on a card (e.g. `D`, `H`) that TCGdex exposes as `regulationMark`. The primary determinant of Standard legality: cards rotate out by mark.
_Avoid_: block letter, rotation letter.

**Standard-legal**:
Whether a card may be played in the Standard format *right now* — computed by this project from the regulation mark against the current allowed range, minus the ban list, with basic Energy always legal. Not taken from TCGdex's `legal.standard`, which is kept only as a reconciliation signal.
_Avoid_: legal, tournament-legal.

**Basic Energy exception**:
Basic Energy cards are Standard-legal in every rotation regardless of regulation mark, and are exempt from the 4-copy deck rule. Identified by category `Energy` + energy type `Basic`.
_Avoid_: energy exemption.

**Ban list**:
The small, project-maintained set of specific cards disallowed in Standard despite an otherwise-legal regulation mark. An input to the Standard-legal computation.
_Avoid_: banlist, restricted list.

**Rotation**:
The periodic advance of the allowed regulation-mark range that drops the oldest marks from Standard. Handled by editing one config value and re-deriving Standard-legal — never by hand-flipping individual cards.
_Avoid_: format rotation, cutoff change.
