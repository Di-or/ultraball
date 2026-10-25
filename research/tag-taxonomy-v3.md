# Functional-Tag Taxonomy — v3

> v2 ([`tag-taxonomy-v2.md`](tag-taxonomy-v2.md)) with `switch` narrowed to real switching and one
> new tag, `retreat-reduction`, split out of it, from [issue #89](https://github.com/Di-or/ultraball/issues/89).
> Every other tag and definition is unchanged from v2. See [What changed from v2](#what-changed-from-v2).
> v1 is [`tag-taxonomy-v1.md`](tag-taxonomy-v1.md).

The curated, enum-constrained vocabulary of **what a card does**. The offline enrichment pass
tags every card *from this list only*; the query rewriter reuses the same words, so a search for
"acceleration" aligns with cards tagged `acceleration`. This is the backbone of the
conceptual-search differentiator.

Bootstrapped **propose → cluster → curate** from recurring Standard-format mechanics.
**29 tags across 7 families.**

## Vocabulary contracts

1. **Multi-label.** A card carries *every* tag that applies (`["draw", "search"]` is normal).
2. **Enum-constrained.** The enricher picks only from this list — constrained decoding guarantees
   it cannot invent a tag.
3. **Effects, not attributes.** HP, stage, Pokémon type, supertype (Item/Supporter/Stadium/Tool),
   EX/ex/V status and printed Retreat Cost stay as DB columns the hard **filter gate** reads. The
   taxonomy never re-encodes them. *(Q1)*
4. **`suggested_new_tag` escape hatch.** When a card's effect fits nothing, the pass emits a
   free-text `suggested_new_tag`. It never enters the live enum — it feeds a review queue that
   grows later versions (ties to the fall-through-logging story).
5. **Versioned.** Each card stores the `taxonomy_version` it was tagged under. A version bump
   re-tags only affected cards — idempotent, incremental, resumable.

## Locked design decisions (Q1–Q6)

| # | Decision | Resolution |
|---|----------|------------|
| Q1 | Effects vs. attributes | **Effects only.** No structural attribute enters the enum; those are filter-gate DB fields. |
| Q2 | Quantitative "power" tags | **Excluded.** No `high-damage`/`OHKO`. Raw damage → numeric field + semantic search; the vocabulary stays qualitative. |
| Q3 | `gust` vs. `switch` | **Split.** They target opposite sides — `gust` drags the opponent's Bench up; `switch` swaps your own Active out. An effect that does both carries both. |
| Q4 | Enum shape | **Flat.** The model emits a flat list of slugs. The 7 families are **documentation only** — no `category` field is stored. Revisit only if the UI wants family grouping. |
| Q5 | Card-type coverage | **One unified list** across all supertypes (Pokémon / Trainer / Energy). |
| Q6 | Tag count | **Ship 27.** Every tag maps to a real, queryable archetype; `suggested_new_tag` grows the rest from real data. v2 added `counter-placement`; v3 adds `retreat-reduction`. |

## What changed from v2

v3 narrows `switch` and adds `retreat-reduction` to the Tempo & positioning family. No other tag
or definition changed.

v2 defined `switch` as "Move *your own* Active to the Bench, or reduce your retreat cost", with
Big Air Balloon, a retreat-cost Tool, as one of its two examples. In the rules these are different
mechanics. Switching is not retreating: it doesn't pay a Retreat Cost, it doesn't use up the one
retreat a turn, and it works when the Active Pokémon can't retreat. A retreat-cost effect only
makes a normal retreat cheaper, so it does nothing against a retreat lock. Folding both into one
tag meant a search for one returned the other. In the #85 parse eval, "retreat for free" was tagged
`switch` on every gpt-5-mini run. Decisions:

- **`switch` is switching only.** "Switch your Active Pokémon with one of your Benched Pokémon."
  That covers Items (Switch `sv01-194`, Scramble Switch `sv08-186`), Supporters (Surfer `sv08-187`,
  AZ's Tranquility `me04-076`), Abilities (Meowscarada `sv09-018`, Mega Dragonite ex `me02.5-152`)
  and attacks (Magnemite's Magnetic Switch `sv01-063`). A Benched Pokémon that switches itself into
  the Active Spot (Minior `sv04-099`, Linoone `me02-082`) is the same swap.
- **`retreat-reduction` is new.** "Reduce or remove your Pokémon's Retreat Cost." That covers Tools
  (Big Air Balloon `sv03.5-155`, Rescue Board `sv08.5-126`), Stadiums (Beach Court `sv01-167`),
  Special Energy (Magnetic Metal Energy `me04-085`) and Abilities, whether they lower one Pokémon's
  cost (Ethan's Magcargo `sv10-036`) or the whole side's (Dragonite `sv03.5-149`). A Stadium that
  lowers both players' costs still carries it.
- **Printed 0 Retreat Cost is a stat, not an effect.** A Pokémon whose printed Retreat Cost is 0
  does **not** get `retreat-reduction`; the `retreat` filter handles it (contract 3). The text the
  enrichment model reads already leaves out the `retreat` value, so the enricher can't tag it from
  the stat.
- **Raising the opponent's cost is not `retreat-reduction`.** Spidops ex's Trap Territory
  `sv01-019` and Calamitous Wasteland `sv02-175` make retreating dearer. `retreat-reduction` is
  about your own Pokémon.
- **Both players switch → `gust` + `switch`.** Effects where you switch your Active and the
  opponent's Active is also switched out (Escape Rope-style: Iron Bundle's Interjet `sv06-062`,
  Baltoy `sv03-094`, Prime Catcher `sv08.5-119`) carry both tags, even when the opponent picks
  their new Active. Decided by the maintainer during triage.
- **`movement-lock` is unchanged.** See the confusion-pair note under Tempo & positioning.
- **Parse prompt.** The same bump adds two rules to the parse prompt. Numeric filters (`retreat`,
  `hp`, `attack_cost`) are filled only when the query states a number or describes the card's
  printed stat ("0 retreat", "no retreat cost", "free retreat Pokémon"). Phrasing about doing
  something ("retreat for free", "switch out") goes to `concept` and `tags`. And the same words are
  never encoded in both `filters` and `concept`. `filters` is a hard gate and Trainers have no
  retreat value, so a `retreat` = 0 filter on "retreat for free" removed every Switch-type and
  retreat-cost Trainer the query was looking for.
- **Re-tag scope.** Contract 5 asks a bump to re-tag only affected cards, but the enrichment queue
  keys on one global `(taxonomy_version, prompt_version)` stamp (CONTEXT.md: Enrichment identity),
  so the v3 bump re-queues every card, as v2 did. That still costs nothing before the first real
  enrichment run. Narrowing it to cards whose text switches or changes a Retreat Cost is left for
  when a re-run has a real cost.
- **Examples.** Big Air Balloon moves from `switch` to `retreat-reduction`, beside Toedscruel
  `sv09-089` for the Ability form. `switch` keeps Switch and gains Magnemite. Surfer and Gengar
  `sv04.5-057` also switch but carry other tags too (`draw`, `special-condition`), and Kieran
  `sv08.5-113` offers switching as one of two modes, so none of them shows the effect in isolation.
  Latias ex `sv08-076` (Skyliner, `retreat-reduction`) is left out as a likely hero-set card.

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
| `counter-placement` | Put damage counters directly on any of the opponent's Pokémon (Active, Benched, or both), rather than dealing damage, so Weakness, Resistance and damage-reduction don't apply. Retaliation when your Pokémon is hit is `counter-damage`. | Drifblim (`sv01-090`), Dusclops (`sv06.5-019`) |

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
| `switch` | Switch your Active Pokémon with one of your Benched Pokémon. Not retreating, so it works even when retreat is blocked. | Switch (`sv01-194`), Magnemite (`sv01-063`) |
| `retreat-reduction` | Reduce or remove your Pokémon's Retreat Cost. | Big Air Balloon (`sv03.5-155`), Toedscruel (`sv09-089`) |
| `evolution-accel` | Evolve faster or skip an evolution step / turn-in-play rule. | Rare Candy (`sv01-191`), Scatterbug (`sv01-008`) |

**Confusion pairs.** `switch`, `retreat-reduction` and `movement-lock` all touch getting a Pokémon
out of the Active Spot, but they are three different effects. `switch` swaps your Active with a
Benched Pokémon without retreating, so it ignores Retreat Cost and works even when retreat is
blocked. `retreat-reduction` makes your own normal retreat cheaper or free, which does nothing if
retreating is blocked. `movement-lock` is the opponent-facing effect that stops retreating or
switching. Many locks only block retreating (Tarountula's Bind Down: "the Defending Pokémon can't
retreat"), and `switch` gets around those, while `retreat-reduction` doesn't. A Pokémon with a
printed Retreat Cost of 0 carries none of the three; that is the `retreat` filter. Effects where
both players switch carry `gust` + `switch`.

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
gust, switch, retreat-reduction, evolution-accel,
healing, condition-heal, damage-reduction, damage-prevention, counter-damage,
prize-manipulation, stall
```

Plus the reserved out-of-band field `suggested_new_tag` (free text, never part of the enum).

## Downstream consumers

- **#5 — offline enrichment pipeline**: tags cards from this enum; carries `taxonomy_version` (`v3`).
- **#8 — query parse & concept rewrite**: rewrites use this vocabulary/definitions so queries
  align with both the tag layer and the embedded descriptions.
- **Later versions**: `suggested_new_tag` + fall-through query logging (fogged on the map).
