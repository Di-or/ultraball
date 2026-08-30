# Functional-Tag Taxonomy — v1 (LOCKED)

> Resolves [issue #2 — Draft the v1 functional-tag taxonomy](https://github.com/Di-or/ultraball/issues/2),
> a child of [the MVP-spec map (#1)](https://github.com/Di-or/ultraball/issues/1).
> React-to draft (as presented for the lock): https://claude.ai/code/artifact/7b003c76-3159-43d3-99f5-0f34e3e6db8f

The curated, enum-constrained vocabulary of **what a card does**. The offline enrichment pass
tags every card *from this list only*; the query rewriter reuses the same words, so a search for
"acceleration" aligns with cards tagged `acceleration`. This is the backbone of the
conceptual-search differentiator.

Bootstrapped **propose → cluster → curate** from recurring Standard-format mechanics.
**27 tags across 7 families.**

## Vocabulary contracts

1. **Multi-label.** A card carries *every* tag that applies (`["draw", "search"]` is normal).
2. **Enum-constrained.** The enricher picks only from this list — constrained decoding guarantees
   it cannot invent a tag.
3. **Effects, not attributes.** HP, stage, Pokémon type, supertype (Item/Supporter/Stadium/Tool),
   and EX/ex/V status stay as DB columns the hard **filter gate** reads. The taxonomy never
   re-encodes them. *(Q1)*
4. **`suggested_new_tag` escape hatch.** When a card's effect fits nothing, the pass emits a
   free-text `suggested_new_tag`. It never enters the live enum — it feeds a review queue that
   grows v2 (ties to the fall-through-logging story).
5. **Versioned.** Each card stores the `taxonomy_version` it was tagged under. A version bump
   re-tags only affected cards — idempotent, incremental, resumable.

## Locked design decisions (Q1–Q6)

| # | Decision | Resolution |
|---|----------|------------|
| Q1 | Effects vs. attributes | **Effects only.** No structural attribute enters the enum; those are filter-gate DB fields. |
| Q2 | Quantitative "power" tags | **Excluded.** No `high-damage`/`OHKO`. Raw damage → numeric field + semantic search; the vocabulary stays qualitative. |
| Q3 | `gust` vs. `switch` | **Split.** They target opposite sides — `gust` drags the opponent's Bench up; `switch` retreats your own. |
| Q4 | Enum shape | **Flat.** The model emits a flat list of slugs. The 7 families are **documentation only** — no `category` field is stored in v1. Revisit in v2 only if the UI wants family grouping. |
| Q5 | Card-type coverage | **One unified list** across all supertypes (Pokémon / Trainer / Energy). |
| Q6 | Tag count | **Ship 27.** Every tag maps to a real, queryable archetype; `suggested_new_tag` grows the rest from real data. |

## The tags

Families organize this document for humans; they are **not** stored (Q4). Each definition is the
one-liner the enricher and the query-rewriter share.

### 1 · Card advantage (resources)

| tag | definition | example |
|-----|------------|---------|
| `draw` | Net-positive draw: puts cards from your deck into your hand. | Professor's Research |
| `search` | Fetch a specific card (by name, type, or trait) from your deck to hand or Bench. | Ultra Ball, Nest Ball |
| `recovery` | Return Pokémon or Trainer cards from your discard pile to hand or deck. | Super Rod, Night Stretcher |

### 2 · Energy

| tag | definition | example |
|-----|------------|---------|
| `acceleration` | Attach Energy beyond your one normal manual attachment per turn. | Baxcalibur, Elesa's Sparkle |
| `energy-search` | Search your deck specifically for Energy cards. | Professor's Letter |
| `energy-recovery` | Return Energy from your discard pile to hand or deck. | Energy Recycler, Superior Energy Retrieval |
| `energy-removal` | Discard or move Energy off the *opponent's* Pokémon. | Enhanced Hammer |

### 3 · Offense — damage shaping

| tag | definition | example |
|-----|------------|---------|
| `spread` | Deal damage to multiple of the opponent's Pokémon at once. | attacks hitting all opposing Pokémon |
| `snipe` | Deal damage to a chosen *Benched* Pokémon, bypassing the Active. | bench-targeting attacks (countered by Manaphy) |
| `damage-scaling` | Attack damage grows with a game-state count — Energy attached, damage counters, cards discarded. | "20× each Energy" attacks |
| `recoil` | Attack costs damage to, or discards Energy from, *your own* Pokémon. | self-damaging attackers |

### 4 · Disruption — control

| tag | definition | example |
|-----|------------|---------|
| `hand-disruption` | Shrink, shuffle away, or force a reveal of the opponent's hand. | Iono, Judge, Roxanne |
| `mill` | Make the opponent discard cards from their deck (deck-out pressure). | Durant-style deck-out |
| `ability-lock` | Turn off the opponent's Abilities. | Path to the Peak |
| `item-lock` | Prevent the opponent from playing Item cards. | item-lock attackers |
| `special-condition` | Inflict Asleep, Burned, Confused, Paralyzed, or Poisoned. | status attackers |
| `movement-lock` | Prevent the opponent from retreating or switching. | no-retreat effects |

### 5 · Tempo & positioning

| tag | definition | example |
|-----|------------|---------|
| `gust` | Force the opponent to switch — drag a Benched Pokémon into the Active spot. | Boss's Orders, Cross Switcher |
| `switch` | Move *your own* Active to the Bench, or reduce your retreat cost. | Switch, Air Balloon |
| `evolution-accel` | Evolve faster or skip an evolution step / turn-in-play rule. | Rare Candy |

### 6 · Defense & survivability

| tag | definition | example |
|-----|------------|---------|
| `healing` | Remove damage counters from your Pokémon. | Potion, Cheren's Care |
| `condition-heal` | Remove Special Conditions from your Pokémon. | Full Heal |
| `damage-reduction` | Reduce the damage your Pokémon take from the opponent's attacks. | Mimikyu, defensive Tools |
| `damage-prevention` | Fully prevent damage or effects under a condition (protect the Bench, block next turn). | Manaphy, "prevent all effects" attacks |
| `counter-damage` | Deal damage back to an attacker when your Pokémon is hit. | Rocky Helmet |

### 7 · Prize & win condition

| tag | definition | example |
|-----|------------|---------|
| `prize-manipulation` | Change how Prizes are taken — extra Prizes on KO, or denying the opponent Prizes. | extra-prize attackers, prize-denial effects |
| `stall` | Waste the opponent's turn or stall the game without trading KOs — block attacks, force skips, run the clock. | lock/stall control shells |

## Enum (flat, for the enricher schema)

```
draw, search, recovery,
acceleration, energy-search, energy-recovery, energy-removal,
spread, snipe, damage-scaling, recoil,
hand-disruption, mill, ability-lock, item-lock, special-condition, movement-lock,
gust, switch, evolution-accel,
healing, condition-heal, damage-reduction, damage-prevention, counter-damage,
prize-manipulation, stall
```

Plus the reserved out-of-band field `suggested_new_tag` (free text, never part of the enum).

## Downstream consumers

- **#5 — offline enrichment pipeline**: tags cards from this enum; carries `taxonomy_version`.
- **#8 — query parse & concept rewrite**: rewrites use this vocabulary/definitions so queries
  align with both the tag layer and the embedded descriptions.
- **v2 growth**: `suggested_new_tag` + fall-through query logging (fogged on the map).
