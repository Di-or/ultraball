# Functional-Tag Taxonomy — v2

> v1 ([`tag-taxonomy-v1.md`](tag-taxonomy-v1.md), resolving [issue #2](https://github.com/Di-or/ultraball/issues/2)) plus one tag,
> `counter-placement`, from [issue #83](https://github.com/Di-or/ultraball/issues/83). Every other tag and definition is unchanged from
> v1. See [What changed from v1](#what-changed-from-v1).

The curated, enum-constrained vocabulary of **what a card does**. The offline enrichment pass
tags every card *from this list only*; the query rewriter reuses the same words, so a search for
"acceleration" aligns with cards tagged `acceleration`. This is the backbone of the
conceptual-search differentiator.

Bootstrapped **propose → cluster → curate** from recurring Standard-format mechanics.
**28 tags across 7 families.**

## Vocabulary contracts

1. **Multi-label.** A card carries *every* tag that applies (`["draw", "search"]` is normal).
2. **Enum-constrained.** The enricher picks only from this list — constrained decoding guarantees
   it cannot invent a tag.
3. **Effects, not attributes.** HP, stage, Pokémon type, supertype (Item/Supporter/Stadium/Tool),
   and EX/ex/V status stay as DB columns the hard **filter gate** reads. The taxonomy never
   re-encodes them. *(Q1)*
4. **`suggested_new_tag` escape hatch.** When a card's effect fits nothing, the pass emits a
   free-text `suggested_new_tag`. It never enters the live enum — it feeds a review queue that
   grows later versions, as it was meant to grow v2 (ties to the fall-through-logging story).
5. **Versioned.** Each card stores the `taxonomy_version` it was tagged under. A version bump
   re-tags only affected cards — idempotent, incremental, resumable.

## Locked design decisions (Q1–Q6)

| # | Decision | Resolution |
|---|----------|------------|
| Q1 | Effects vs. attributes | **Effects only.** No structural attribute enters the enum; those are filter-gate DB fields. |
| Q2 | Quantitative "power" tags | **Excluded.** No `high-damage`/`OHKO`. Raw damage → numeric field + semantic search; the vocabulary stays qualitative. |
| Q3 | `gust` vs. `switch` | **Split.** They target opposite sides — `gust` drags the opponent's Bench up; `switch` retreats your own. |
| Q4 | Enum shape | **Flat.** The model emits a flat list of slugs. The 7 families are **documentation only** — no `category` field is stored. Revisit only if the UI wants family grouping. |
| Q5 | Card-type coverage | **One unified list** across all supertypes (Pokémon / Trainer / Energy). |
| Q6 | Tag count | **Ship 27.** Every tag maps to a real, queryable archetype; `suggested_new_tag` grows the rest from real data. v2 adds one (below). |

## What changed from v1

v2 adds `counter-placement` to the Offense family. No v1 tag or definition changed.

In the rules, putting damage counters on a Pokémon is not damage. Weakness, Resistance and
damage-reduction don't apply to it, and effects that only prevent damage don't stop it. v1 had no
tag for it. The nearest tags, `spread` and `snipe`, both say "deal damage", so the enricher and the
parser could each read Dragapult ex's Phantom Dive as `snipe`, as `spread`, or as neither. It is
also an archetype players search for by name ("bench damage counters", "Dusknoir"). About 39
Scarlet & Violet–Mega Evolution cards place counters on the opponent's Pokémon, through attacks,
Abilities, Pokémon Checkup effects and one Item (Team Rocket's Venture Bomb `sv10-179`).

It ships ahead of `suggested_new_tag` data (contract 4) on that evidence, since no enrichment run
has happened yet. Decisions:

- **Name.** `counter-placement`, not `damage-counters`, which reads too close to `counter-damage`.
- **Orthogonal to `spread` and `snipe`.** Those still mean damage. A card that only places counters
  on the Bench (Dragapult ex `sv06-130`) carries `counter-placement`, not `snipe`. An attack that
  both deals damage and places counters carries both tags. A query that doesn't say which ("hit the
  bench") can be parsed to both.
- **Not retaliation.** In Scarlet & Violet, retaliation is almost always counters on the
  Attacking Pokémon (Rocky Helmet, Cacturne). That stays `counter-damage` only, which the definition
  says, so `counter-placement` doesn't swallow `counter-damage`.
- **Timing.** Delayed counters (Glaceon `sv06-054`) and Pokémon Checkup counters (Trevenant
  `sv03-012`) count, because the effect is the same.
- **Opponent's side only.** Moving or removing damage counters among your own Pokémon is out of
  scope. Moving counters from your Pokémon onto the opponent's (Munkidori `sv06-095`) does put them
  on the opponent's Pokémon.
- **Re-tag scope.** Contract 5 asks a bump to re-tag only affected cards, but the enrichment queue
  keys on one global `(taxonomy_version, prompt_version)` stamp (CONTEXT.md: Enrichment identity),
  so the v2 bump re-queues every card. That costs nothing before the first real enrichment run.
  Narrowing it to cards whose text places counters is left for when a re-run has a real cost.
- **Examples.** Mimikyu `sv02-097` (Ghost Eye) and Flutter Mane `sv05-078` (Hex Hurl) also place
  counters, which is fine under multi-label (contract 1), but they also carry other tags, so they
  aren't examples here. Nor is Dusknoir `sv06.5-020`: its Shadow Bind is `movement-lock`. Dragapult
  ex is left out as a likely hero-set card.

## The tags

Families organize this document for humans; they are **not** stored (Q4). Each definition is the
one-liner the enricher and the query-rewriter share. Definitions and examples are mirrored in
`app/enrichment/taxonomy.py` (`TAG_DEFINITIONS`, `TAG_EXAMPLES`), and a test keeps the two in step.
Examples are real Scarlet & Violet–Mega Evolution cards cited by TCGdex id, checked against their
card text; none come from the gold or hero set. Each example carries only the tag it illustrates,
across all of its attacks and Abilities, so the effect is shown in isolation.

### 1 · Card advantage (resources)

| tag | definition | example |
|-----|------------|---------|
| `draw` | Net-positive draw: puts cards from your deck into your hand. | Dudunsparce (`sv05-129`), Carmine (`sv06-145`) |
| `search` | Fetch a specific card (by name, type, or trait) from your deck to hand or Bench. | Nest Ball (`sv01-181`), Pidgeot ex (`sv03-164`) |
| `recovery` | Return Pokémon or Trainer cards from your discard pile to hand or deck. | Pal Pad (`sv01-182`), Miracle Headset (`sv08-183`) |

### 2 · Energy

| tag | definition | example |
|-----|------------|---------|
| `acceleration` | Attach Energy beyond your one normal manual attachment per turn. | Baxcalibur (`sv02-060`), Barbaracle (`me03-043`) |
| `energy-search` | Search your deck specifically for Energy cards. | Earthen Vessel (`sv04-163`) |
| `energy-recovery` | Return Energy from your discard pile to hand or deck. | Energy Retrieval (`sv01-171`), Energy Recycler (`sv10-164`) |
| `energy-removal` | Discard or move Energy off the *opponent's* Pokémon. | Enhanced Hammer (`sv06-148`), Crushing Hammer (`sv01-168`) |

### 3 · Offense — damage shaping

| tag | definition | example |
|-----|------------|---------|
| `spread` | Deal damage to multiple of the opponent's Pokémon at once. | Lapras (`sv03-045`), Regice (`sv09-042`) |
| `snipe` | Deal damage to a chosen *Benched* Pokémon, bypassing the Active. | Golbat (`sv03.5-042`), Elekid (`sv04-059`) |
| `damage-scaling` | Attack damage grows with a game-state count — Energy attached, damage counters, cards discarded. | Chandelure (`sv03-038`), Drampa (`sv03-161`) |
| `recoil` | Attack costs damage to, or discards Energy from, *your own* Pokémon. | Koraidon (`sv01-124`), Primeape (`sv01-108`) |
| `counter-placement` | Put damage counters directly on the opponent's Pokémon, rather than dealing damage, so Weakness, Resistance and damage-reduction don't apply. Retaliation when your Pokémon is hit is `counter-damage`. | Drifblim (`sv01-090`), Dusclops (`sv06.5-019`) |

**Confusion pairs.** `spread` and `snipe` deal damage; `counter-placement` puts damage counters on
the opponent's Pokémon without dealing damage. `counter-damage` covers hitting back when your
Pokémon is hit, whether by damage or counters. Drifblim's Curse Spreading shows the attack form and
Dusclops's Cursed Blast the Ability form.

### 4 · Disruption — control

| tag | definition | example |
|-----|------------|---------|
| `hand-disruption` | Shrink, shuffle away, or force a reveal of the opponent's hand. | Grabber (`sv03.5-162`), Krokorok (`sv10.5b-058`) |
| `mill` | Make the opponent discard cards from their deck (deck-out pressure). | Zweilous (`sv08-118`) |
| `ability-lock` | Turn off the opponent's Abilities. | Klefki (`sv01-096`) |
| `item-lock` | Prevent the opponent from playing Item cards. | Budew (`sv08.5-004`) |
| `special-condition` | Inflict Asleep, Burned, Confused, Paralyzed, or Poisoned. | Toedscool (`sv01-025`) |
| `movement-lock` | Prevent the opponent from retreating or switching. | Tarountula (`sv02-016`), Corvisquire (`sv02-165`) |

### 5 · Tempo & positioning

| tag | definition | example |
|-----|------------|---------|
| `gust` | Force the opponent to switch — drag a Benched Pokémon into the Active spot. | Pokémon Catcher (`sv01-187`), Gloom (`sv03-002`) |
| `switch` | Move *your own* Active to the Bench, or reduce your retreat cost. | Switch (`sv01-194`), Big Air Balloon (`sv03.5-155`) |
| `evolution-accel` | Evolve faster or skip an evolution step / turn-in-play rule. | Rare Candy (`sv01-191`), Scatterbug (`sv01-008`) |

### 6 · Defense & survivability

| tag | definition | example |
|-----|------------|---------|
| `healing` | Remove damage counters from your Pokémon. | Potion (`sv01-188`), Cook (`sv06-147`) |
| `condition-heal` | Remove Special Conditions from your Pokémon. | Blissey (`sv01-145`), Therapeutic Energy (`sv02-193`) |
| `damage-reduction` | Reduce the damage your Pokémon take from the opponent's attacks. | Rock Chestplate (`sv01-192`), Stonjourner (`sv01-121`) |
| `damage-prevention` | Fully prevent damage or effects under a condition (protect the Bench, block next turn). | Shaymin (`sv10-010`), Hoppip (`sv02-001`) |
| `counter-damage` | Deal damage back to an attacker when your Pokémon is hit. | Rocky Helmet (`sv01-193`), Cacturne (`sv01-006`) |

### 7 · Prize & win condition

| tag | definition | example |
|-----|------------|---------|
| `prize-manipulation` | Change how Prizes are taken — extra Prizes on KO, or denying the opponent Prizes. | Iron Hands ex (`sv04-070`), Legacy Energy (`sv06-167`) |
| `stall` | Waste the opponent's turn or stall the game without trading KOs — block attacks, force skips, run the clock. | Lickitung (`sv03.5-108`), Frosmoth (`sv05-046`) |

## Enum (flat, for the enricher schema)

```
draw, search, recovery,
acceleration, energy-search, energy-recovery, energy-removal,
spread, snipe, damage-scaling, recoil, counter-placement,
hand-disruption, mill, ability-lock, item-lock, special-condition, movement-lock,
gust, switch, evolution-accel,
healing, condition-heal, damage-reduction, damage-prevention, counter-damage,
prize-manipulation, stall
```

Plus the reserved out-of-band field `suggested_new_tag` (free text, never part of the enum).

## Downstream consumers

- **#5 — offline enrichment pipeline**: tags cards from this enum; carries `taxonomy_version` (`v2`).
- **#8 — query parse & concept rewrite**: rewrites use this vocabulary/definitions so queries
  align with both the tag layer and the embedded descriptions.
- **Later versions**: `suggested_new_tag` + fall-through query logging (fogged on the map).
