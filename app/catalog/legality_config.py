# Rotation is a config edit + re-derive, never per-card hand-flipping (CONTEXT.md: Rotation).
#
# To advance the rotation: update STANDARD_LEGAL_MARKS to the new allowed window, then
# re-run ingest (or a re-derive pass) so every card's `is_standard_legal` is recomputed.
STANDARD_LEGAL_MARKS: frozenset[str] = frozenset({"G", "H", "I"})

# Cards banned from Standard despite an otherwise-legal regulation mark, keyed by
# dedupe_key (CONTEXT.md: Ban list). Empty until the project's first ban.
BANNED_DEDUPE_KEYS: frozenset[str] = frozenset()
