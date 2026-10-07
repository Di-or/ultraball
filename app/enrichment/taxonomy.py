from dataclasses import dataclass

# The v2 functional-tag taxonomy — 28 effects-only tags across 7 documentation-only
# families (v1 plus `counter-placement`, #83). Flat enum in code (Q4): the enricher
# and the query rewriter share this exact vocabulary. See CONTEXT.md: Functional tag.
TAXONOMY_VERSION = "v2"

# Bumping the prompt independently of the taxonomy (a wording fix, a confusion-pair
# clarification) still forces a re-pass without needing a taxonomy version bump.
PROMPT_VERSION = "v2"


@dataclass(frozen=True)
class TagExample:
    """A real card that carries a tag, cited by its TCGdex id (set id + number)."""

    name: str
    card_id: str


# One-line definitions, word for word from research/tag-taxonomy-v2.md (a test holds
# the two together). The parse prompt renders from this, and the enrichment prompt
# (#77) is to render from it too, so the enrichment pass and the parser draw the same
# line between neighbouring tags. Changing a definition or example changes both
# prompts: bump PARSE_VERSION (app.search.parse) and PROMPT_VERSION.
TAG_DEFINITIONS: dict[str, str] = {
    # Card advantage (resources)
    "draw": "Net-positive draw: puts cards from your deck into your hand.",
    "search": "Fetch a specific card (by name, type, or trait) from your deck to hand or Bench.",
    "recovery": "Return Pokémon or Trainer cards from your discard pile to hand or deck.",
    # Energy
    "acceleration": "Attach Energy beyond your one normal manual attachment per turn.",
    "energy-search": "Search your deck specifically for Energy cards.",
    "energy-recovery": "Return Energy from your discard pile to hand or deck.",
    "energy-removal": "Discard or move Energy off the *opponent's* Pokémon.",
    # Offense — damage shaping
    "spread": "Deal damage to multiple of the opponent's Pokémon at once.",
    "snipe": "Deal damage to a chosen *Benched* Pokémon, bypassing the Active.",
    "damage-scaling": (
        "Attack damage grows with a game-state count — Energy attached, damage counters, cards discarded."
    ),
    "recoil": "Attack costs damage to, or discards Energy from, *your own* Pokémon.",
    "counter-placement": (
        "Put damage counters directly on the opponent's Pokémon, rather than dealing damage, "
        "so Weakness, Resistance and damage-reduction don't apply. Retaliation when your Pokémon "
        "is hit is `counter-damage`."
    ),
    # Disruption — control
    "hand-disruption": "Shrink, shuffle away, or force a reveal of the opponent's hand.",
    "mill": "Make the opponent discard cards from their deck (deck-out pressure).",
    "ability-lock": "Turn off the opponent's Abilities.",
    "item-lock": "Prevent the opponent from playing Item cards.",
    "special-condition": "Inflict Asleep, Burned, Confused, Paralyzed, or Poisoned.",
    "movement-lock": "Prevent the opponent from retreating or switching.",
    # Tempo & positioning
    "gust": "Force the opponent to switch — drag a Benched Pokémon into the Active spot.",
    "switch": "Move *your own* Active to the Bench, or reduce your retreat cost.",
    "evolution-accel": "Evolve faster or skip an evolution step / turn-in-play rule.",
    # Defense & survivability
    "healing": "Remove damage counters from your Pokémon.",
    "condition-heal": "Remove Special Conditions from your Pokémon.",
    "damage-reduction": "Reduce the damage your Pokémon take from the opponent's attacks.",
    "damage-prevention": (
        "Fully prevent damage or effects under a condition (protect the Bench, block next turn)."
    ),
    "counter-damage": "Deal damage back to an attacker when your Pokémon is hit.",
    # Prize & win condition
    "prize-manipulation": (
        "Change how Prizes are taken — extra Prizes on KO, or denying the opponent Prizes."
    ),
    "stall": (
        "Waste the opponent's turn or stall the game without trading KOs — block attacks, "
        "force skips, run the clock."
    ),
}

FUNCTIONAL_TAGS: frozenset[str] = frozenset(TAG_DEFINITIONS)

# 1–2 cards per tag from Scarlet & Violet through Mega Evolution, checked against
# TCGdex card text. Every example carries only its own tag across all of its attacks
# and Abilities, so each one shows the tag's effect in isolation; that also keeps
# confusion pairs apart (Baxcalibur attaches without searching; Earthen Vessel searches
# without attaching). Never the gold or hero set (CONTEXT.md: Quality validation): an
# example in the prompt would inflate the score that set measures.
TAG_EXAMPLES: dict[str, tuple[TagExample, ...]] = {
    "draw": (TagExample("Dudunsparce", "sv05-129"), TagExample("Carmine", "sv06-145")),
    "search": (TagExample("Nest Ball", "sv01-181"), TagExample("Pidgeot ex", "sv03-164")),
    "recovery": (TagExample("Pal Pad", "sv01-182"), TagExample("Miracle Headset", "sv08-183")),
    "acceleration": (TagExample("Baxcalibur", "sv02-060"), TagExample("Barbaracle", "me03-043")),
    "energy-search": (TagExample("Earthen Vessel", "sv04-163"),),
    "energy-recovery": (
        TagExample("Energy Retrieval", "sv01-171"),
        TagExample("Energy Recycler", "sv10-164"),
    ),
    "energy-removal": (
        TagExample("Enhanced Hammer", "sv06-148"),
        TagExample("Crushing Hammer", "sv01-168"),
    ),
    "spread": (TagExample("Lapras", "sv03-045"), TagExample("Regice", "sv09-042")),
    "snipe": (TagExample("Golbat", "sv03.5-042"), TagExample("Elekid", "sv04-059")),
    "damage-scaling": (TagExample("Chandelure", "sv03-038"), TagExample("Drampa", "sv03-161")),
    "recoil": (TagExample("Koraidon", "sv01-124"), TagExample("Primeape", "sv01-108")),
    "counter-placement": (TagExample("Drifblim", "sv01-090"), TagExample("Dusclops", "sv06.5-019")),
    "hand-disruption": (TagExample("Grabber", "sv03.5-162"), TagExample("Krokorok", "sv10.5b-058")),
    "mill": (TagExample("Zweilous", "sv08-118"),),
    "ability-lock": (TagExample("Klefki", "sv01-096"),),
    "item-lock": (TagExample("Budew", "sv08.5-004"),),
    "special-condition": (TagExample("Toedscool", "sv01-025"),),
    "movement-lock": (TagExample("Tarountula", "sv02-016"), TagExample("Corvisquire", "sv02-165")),
    "gust": (TagExample("Pokémon Catcher", "sv01-187"), TagExample("Gloom", "sv03-002")),
    "switch": (TagExample("Switch", "sv01-194"), TagExample("Big Air Balloon", "sv03.5-155")),
    "evolution-accel": (TagExample("Rare Candy", "sv01-191"), TagExample("Scatterbug", "sv01-008")),
    "healing": (TagExample("Potion", "sv01-188"), TagExample("Cook", "sv06-147")),
    "condition-heal": (
        TagExample("Blissey", "sv01-145"),
        TagExample("Therapeutic Energy", "sv02-193"),
    ),
    "damage-reduction": (
        TagExample("Rock Chestplate", "sv01-192"),
        TagExample("Stonjourner", "sv01-121"),
    ),
    "damage-prevention": (TagExample("Shaymin", "sv10-010"), TagExample("Hoppip", "sv02-001")),
    "counter-damage": (TagExample("Rocky Helmet", "sv01-193"), TagExample("Cacturne", "sv01-006")),
    "prize-manipulation": (
        TagExample("Iron Hands ex", "sv04-070"),
        TagExample("Legacy Energy", "sv06-167"),
    ),
    "stall": (TagExample("Lickitung", "sv03.5-108"), TagExample("Frosmoth", "sv05-046")),
}


def render_tag_glossary() -> str:
    """The tag definitions and example cards as a prompt block, one tag per line.

    Deterministic (definition order, no timestamps) so it can sit at the front of a
    cached prompt prefix.
    """
    lines = []
    for tag, definition in TAG_DEFINITIONS.items():
        examples = ", ".join(example.name for example in TAG_EXAMPLES[tag])
        lines.append(f"- {tag}: {definition} Examples: {examples}.")
    return "\n".join(lines)
