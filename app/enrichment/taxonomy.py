# The v1 functional-tag taxonomy (LOCKED) — 27 effects-only tags across 7
# documentation-only families. Flat enum in code (Q4): the enricher and the query
# rewriter share this exact vocabulary. See CONTEXT.md: Functional tag.
TAXONOMY_VERSION = "v1"

# Bumping the prompt independently of the taxonomy (a wording fix, a confusion-pair
# clarification) still forces a re-pass without needing a taxonomy version bump.
PROMPT_VERSION = "v1"

FUNCTIONAL_TAGS: frozenset[str] = frozenset(
    {
        # Card advantage (resources)
        "draw",
        "search",
        "recovery",
        # Energy
        "acceleration",
        "energy-search",
        "energy-recovery",
        "energy-removal",
        # Offense — damage shaping
        "spread",
        "snipe",
        "damage-scaling",
        "recoil",
        # Disruption — control
        "hand-disruption",
        "mill",
        "ability-lock",
        "item-lock",
        "special-condition",
        "movement-lock",
        # Tempo & positioning
        "gust",
        "switch",
        "evolution-accel",
        # Defense & survivability
        "healing",
        "condition-heal",
        "damage-reduction",
        "damage-prevention",
        "counter-damage",
        # Prize & win condition
        "prize-manipulation",
        "stall",
    }
)
