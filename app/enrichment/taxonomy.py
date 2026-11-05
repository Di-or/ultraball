from dataclasses import dataclass

# The v5 functional-tag taxonomy — 30 effects-only tags across 7 documentation-only
# families (v4 with `damage-prevention` split from `effect-prevention`, `damage-boost` and
# `energy-movement` added, and `energy-search` / `energy-recovery` merged into `search` /
# `recovery`, #103). Flat enum in code (Q4): the enricher and the query rewriter share this
# exact vocabulary. See CONTEXT.md: Functional tag.
TAXONOMY_VERSION = "v5"

# Bumping the prompt independently of the taxonomy (a wording fix, a confusion-pair
# clarification) still forces a re-pass without needing a taxonomy version bump.
PROMPT_VERSION = "v7"


@dataclass(frozen=True)
class TagExample:
    """A real card that carries a tag, cited by its TCGdex id (set id + number).

    `also` names the other tags the card carries; only examples in `BENCH_DAMAGE_TAGS` have any.
    """

    name: str
    card_id: str
    also: tuple[str, ...] = ()


# One-line definitions, word for word from research/tag-taxonomy-v5.md (a test holds
# the two together). The parse prompt renders from this, and the enrichment prompt
# (#77) is to render from it too, so the enrichment pass and the parser draw the same
# line between neighbouring tags. Changing a definition or example changes both
# prompts: bump PARSE_VERSION (app.search.parse) and PROMPT_VERSION.
TAG_DEFINITIONS: dict[str, str] = {
    # Card advantage (resources)
    "draw": (
        "Draw cards from your deck, including discarding or shuffling your hand away and drawing "
        "a new one."
    ),
    "search": (
        "Fetch a specific card (by name, type, or trait, Energy included) from your deck to hand or Bench."
    ),
    "recovery": (
        "Get cards back from your discard pile — into your hand or deck, onto your Bench, "
        "or attached to your Pokémon."
    ),
    # Energy
    "acceleration": "Attach Energy beyond your one normal manual attachment per turn.",
    "energy-movement": "Move Energy from one Pokémon to another, on either player's side.",
    "energy-removal": "The *opponent's* Pokémon loses Energy: discard it, or move it off.",
    # Offense — damage shaping
    "bench-reach": (
        "An attack or Ability can deal damage to, or put damage counters on, "
        "one or more of the opponent's *Benched* Pokémon."
    ),
    "multi-target": (
        "One attack or Ability use can deal damage to, or put damage counters on, more than one "
        "of the opponent's Pokémon (choosing a target several times counts, even if every hit "
        "lands on one)."
    ),
    "damage-scaling": (
        "Attack damage grows with a game-state count — Energy attached, damage counters, cards discarded."
    ),
    "damage-boost": (
        "Make attacks do a fixed amount more damage — from a Tool, Ability, Stadium, Item, Supporter "
        "or Energy, or an attack's own conditional bonus (\"does 100 more damage if…\"). "
        "A per-count increase is `damage-scaling`."
    ),
    "recoil": "An attack or Ability does damage to, or Knocks Out, *your own* Pokémon.",
    "counter-placement": (
        "Put damage counters directly on the opponent's Pokémon rather than dealing damage, "
        "so Weakness, Resistance and damage-reduction don't apply. "
        "Retaliation when your Pokémon is hit is `counter-damage`."
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
    "switch": (
        "Switch your Active Pokémon with one of your Benched Pokémon. "
        "Not retreating, so it works even when retreat is blocked."
    ),
    "retreat-reduction": "Reduce or remove your Pokémon's Retreat Cost.",
    "evolution-accel": "Evolve faster or skip an evolution step / turn-in-play rule.",
    # Defense & survivability
    "healing": "Remove damage counters from your Pokémon.",
    "condition-heal": "Remove Special Conditions from your Pokémon.",
    "damage-reduction": "Reduce the damage your Pokémon take from the opponent's attacks.",
    "damage-prevention": (
        "Prevent the damage the opponent's attacks do to your Pokémon, under a condition "
        "(a Benched Pokémon, next turn)."
    ),
    "effect-prevention": (
        "Prevent the effects of the opponent's attacks or Abilities on your Pokémon, "
        "including damage counters they place."
    ),
    "counter-damage": (
        "When your Pokémon is hit by an attack, punish the Attacking Pokémon — damage, "
        "damage counters, a Knock Out, or another effect such as a Special Condition or losing Energy, "
        "which carries its own tag too."
    ),
    # Prize & win condition
    "prize-manipulation": (
        "Change how Prizes are taken — extra Prizes on KO, or denying the opponent Prizes."
    ),
    "stall": (
        "Stop the opponent from attacking or taking their turn — the Defending Pokémon can't "
        "attack, they skip a turn."
    ),
}

FUNCTIONAL_TAGS: frozenset[str] = frozenset(TAG_DEFINITIONS)

# How a card puts damage on the opponent's Bench, or on several Pokémon, split into one
# question per tag: can it reach the Bench, can one use hit more than one Pokémon, and does
# it use counters instead of damage. They combine freely (Dragapult ex carries all three).
BENCH_DAMAGE_TAGS: frozenset[str] = frozenset({"bench-reach", "multi-target", "counter-placement"})


@dataclass(frozen=True)
class TwoTagRule:
    """An effect that always carries both of two neighbouring tags."""

    effect: str
    tags: tuple[str, str]


# Effects whose definitions overlap, so a card (or query) with one carries both tags. The one
# list both prompts render, word for word from the v5 doc's "Effects that carry two tags" table
# (a test holds the two together); changing it changes both prompts, as for TAG_DEFINITIONS.
TWO_TAG_RULES: tuple[TwoTagRule, ...] = (
    TwoTagRule("Both players switch their Active Pokémon", ("gust", "switch")),
    TwoTagRule(
        "Energy is moved off one of the opponent's Pokémon to another of theirs",
        ("energy-movement", "energy-removal"),
    ),
    TwoTagRule(
        "Every player's hand is reset — shuffled or discarded, then a new one drawn",
        ("draw", "hand-disruption"),
    ),
    TwoTagRule("Energy is attached from your discard pile", ("acceleration", "recovery")),
    TwoTagRule(
        "All damage from and effects of attacks are prevented",
        ("damage-prevention", "effect-prevention"),
    ),
)

# 1–2 cards per tag from Scarlet & Violet through Mega Evolution, checked against
# TCGdex card text. Every example carries only its own tag across all of its attacks
# and Abilities, so each one shows the tag's effect in isolation; that also keeps
# confusion pairs apart (Baxcalibur attaches without searching; Earthen Vessel searches
# without attaching). The exception is BENCH_DAMAGE_TAGS: nearly anything `multi-target`
# is also `bench-reach`, so their examples show the effect clearly and name the others
# they carry in `also`. Never the gold or hero set (CONTEXT.md: Quality validation): an
# example in the prompt would inflate the score that set measures.
TAG_EXAMPLES: dict[str, tuple[TagExample, ...]] = {
    "draw": (TagExample("Dudunsparce", "sv05-129"), TagExample("Carmine", "sv06-145")),
    "search": (TagExample("Nest Ball", "sv01-181"), TagExample("Earthen Vessel", "sv04-163")),
    "recovery": (TagExample("Pal Pad", "sv01-182"), TagExample("Energy Retrieval", "sv01-171")),
    "acceleration": (TagExample("Baxcalibur", "sv02-060"), TagExample("Barbaracle", "me03-043")),
    "energy-movement": (TagExample("Poppy", "sv03-193"), TagExample("Dewgong", "me03-019")),
    "energy-removal": (
        TagExample("Enhanced Hammer", "sv06-148"),
        TagExample("Crushing Hammer", "sv01-168"),
    ),
    "bench-reach": (TagExample("Golbat", "sv03.5-042"), TagExample("Elekid", "sv04-059")),
    "multi-target": (
        TagExample("Lapras", "sv03-045", also=("bench-reach",)),
        TagExample("Regice", "sv09-042", also=("bench-reach",)),
    ),
    "damage-scaling": (TagExample("Chandelure", "sv03-038"), TagExample("Drampa", "sv03-161")),
    "damage-boost": (TagExample("Vitality Band", "sv01-197"), TagExample("Greedent", "sv01-152")),
    "recoil": (TagExample("Primeape", "sv01-108"), TagExample("Magneton", "sv01-064")),
    "counter-placement": (
        TagExample("Drifblim", "sv01-090", also=("bench-reach", "multi-target")),
        TagExample("Iron Valiant ex", "sv04-089", also=("bench-reach",)),
    ),
    "hand-disruption": (TagExample("Grabber", "sv03.5-162"), TagExample("Krokorok", "sv10.5b-058")),
    "mill": (TagExample("Zweilous", "sv08-118"),),
    "ability-lock": (TagExample("Klefki", "sv01-096"),),
    "item-lock": (TagExample("Budew", "sv08.5-004"),),
    "special-condition": (TagExample("Toedscool", "sv01-025"),),
    "movement-lock": (TagExample("Tarountula", "sv02-016"), TagExample("Corvisquire", "sv02-165")),
    "gust": (TagExample("Pokémon Catcher", "sv01-187"), TagExample("Gloom", "sv03-002")),
    "switch": (TagExample("Switch", "sv01-194"), TagExample("Magnemite", "sv01-063")),
    "retreat-reduction": (
        TagExample("Big Air Balloon", "sv03.5-155"),
        TagExample("Toedscruel", "sv09-089"),
    ),
    "evolution-accel": (TagExample("Rare Candy", "sv01-191"), TagExample("Scatterbug", "sv01-008")),
    "healing": (TagExample("Potion", "sv01-188"), TagExample("Cook", "sv06-147")),
    "condition-heal": (
        TagExample("Ancient Booster Energy Capsule", "sv04-159"),
        TagExample("Therapeutic Energy", "sv02-193"),
    ),
    "damage-reduction": (
        TagExample("Rock Chestplate", "sv01-192"),
        TagExample("Stonjourner", "sv01-121"),
    ),
    "damage-prevention": (TagExample("Shaymin", "sv10-010"), TagExample("Glimmet", "sv03-121")),
    "effect-prevention": (TagExample("Mist Energy", "sv05-161"), TagExample("Kakuna", "sv03.5-014")),
    "counter-damage": (TagExample("Rocky Helmet", "sv01-193"), TagExample("Cacturne", "sv01-006")),
    "prize-manipulation": (
        TagExample("Iron Hands ex", "sv04-070"),
        TagExample("Legacy Energy", "sv06-167"),
    ),
    "stall": (TagExample("Lickitung", "sv03.5-108"), TagExample("Frosmoth", "sv05-046")),
}


def _render_example(example: TagExample) -> str:
    return f"{example.name} (also {', '.join(example.also)})" if example.also else example.name


def render_tag_glossary() -> str:
    """The tag definitions and example cards as a prompt block, one tag per line.

    Deterministic (definition order, no timestamps) so it can sit at the front of a
    cached prompt prefix.
    """
    lines = []
    for tag, definition in TAG_DEFINITIONS.items():
        examples = ", ".join(_render_example(example) for example in TAG_EXAMPLES[tag])
        lines.append(f"- {tag}: {definition} Examples: {examples}.")
    return "\n".join(lines)


def render_two_tag_rules() -> str:
    """The effects that carry two tags as a prompt block, one per line, in list order."""
    lines = ["Effects that carry two tags (a card or query with one of these gets both):"]
    lines += [f"- {rule.effect}: `{rule.tags[0]}` + `{rule.tags[1]}`." for rule in TWO_TAG_RULES]
    return "\n".join(lines)
