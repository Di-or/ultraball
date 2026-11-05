# Functional-Tag Taxonomy — v5

> v4 ([`tag-taxonomy-v4.md`](tag-taxonomy-v4.md)) with `damage-prevention` split into
> `damage-prevention` and `effect-prevention`, `damage-boost` and `energy-movement` added,
> `energy-search` and `energy-recovery` merged into `search` and `recovery`, `recoil` narrowed, and
> `counter-damage`, `stall`, `draw` and `energy-removal` reworded, from
> [issue #103](https://github.com/Di-or/ultraball/issues/103). See
> [What changed from v4](#what-changed-from-v4).
> v1–v3 are [`tag-taxonomy-v1.md`](tag-taxonomy-v1.md), [`tag-taxonomy-v2.md`](tag-taxonomy-v2.md)
> and [`tag-taxonomy-v3.md`](tag-taxonomy-v3.md).

The curated, enum-constrained vocabulary of **what a card does**. The offline enrichment pass
tags every card *from this list only*; the query rewriter reuses the same words, so a search for
"acceleration" aligns with cards tagged `acceleration`. This is the backbone of the
conceptual-search differentiator.

Bootstrapped **propose → cluster → curate** from recurring Standard-format mechanics.
**30 tags across 7 families.**

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
| Q2 | Quantitative "power" tags | **Excluded.** No `high-damage`/`OHKO`. Raw damage → numeric field + semantic search; the vocabulary stays qualitative. `damage-boost` is qualitative too: it says an effect adds damage, not how much. |
| Q3 | `gust` vs. `switch` | **Split.** They target opposite sides — `gust` drags the opponent's Bench up; `switch` swaps your own Active out. An effect that does both carries both. |
| Q4 | Enum shape | **Flat.** The model emits a flat list of slugs. The 7 families are **documentation only** — no `category` field is stored. Revisit only if the UI wants family grouping. |
| Q5 | Card-type coverage | **One unified list** across all supertypes (Pokémon / Trainer / Energy). |
| Q6 | Tag count | **Ship 27** (30 since v5). Every tag maps to a real, queryable archetype; `suggested_new_tag` grows the rest from real data. v2 added `counter-placement`; v3 added `retreat-reduction`; v4 swapped `snipe`/`spread` for `bench-reach`/`multi-target`; v5 adds `effect-prevention`, `damage-boost` and `energy-movement` and folds `energy-search` and `energy-recovery` into `search` and `recovery`. |

## What changed from v4

The tag count goes from 29 to 30. No tag outside the table changed.

| Change | Tags | Count |
|---|---|---|
| Split | `damage-prevention` → `damage-prevention` + `effect-prevention` | +1 |
| New | `damage-boost` | +1 |
| New | `energy-movement` | +1 |
| Merge | `energy-search` into `search` | −1 |
| Merge | `energy-recovery` into `recovery` (widened) | −1 |
| Narrow | `recoil` (self-damage and self-KO only) | 0 |
| Reword | `counter-damage`, `stall`, `draw`, `energy-removal` | 0 |
| Unchanged | `prize-manipulation` (covers both sides, kept on purpose) | 0 |

Several v4 tags had the flaw `snipe` and `spread` had: one tag answered two questions, or a
definition didn't match its own examples. A few common effects had no tag.

- **`damage-prevention` mixed damage and effects.** "Fully prevent damage *or effects*" put
  Shaymin (`sv10-010`, Flower Curtain: prevents attack damage to the Bench) and Sinistcha
  (`me05-006`, Hide 'n' Sneak: prevents effects of attacks and Abilities) under one tag. Since v4
  that matters more: damage counters get past damage prevention but not effect prevention, so
  "protect my bench from Dragapult" couldn't be told apart from "protect my bench from damage".
- **`recoil` mixed self-damage and Energy discard.** The first v4 live run tagged Kyurem
  (`sv06.5-047`, Trifrost: "Discard all Energy from this Pokémon") `recoil` for the Energy discard
  alone, so "attackers that hurt themselves" also returned every Energy-discard attacker. It also
  said "Attack", which left out a self-KO Ability (Dusclops's Cursed Blast).
- **`counter-damage` contradicted its examples.** It said "Deal damage back", but both examples
  place damage counters (Rocky Helmet `sv01-193`, Cacturne `sv01-006`). The live run also tagged
  Gengar ex (`30th-090`, Fainting Spell: flip to Knock Out the attacker) `counter-damage`, which
  isn't damage either.
- **`stall` and `damage-prevention` both said "block".** "Block attacks" (the Defending Pokémon
  can't attack) and "block next turn" (prevent all damage done to this Pokémon) are different
  effects under the same verb.
- **`search` and `energy-search` overlapped.** `search` ("by name, type, or trait") already covered
  Energy, yet the single-tag example rule said Earthen Vessel carried only `energy-search`.
- **Recovery was split by card type and destination.** `recovery` (Pokémon or Trainers to hand or
  deck) and `energy-recovery` (Energy to hand or deck) left out attaching from the discard and
  discard-to-Bench, so "get energy back from the discard" missed a card that attaches Energy from
  the discard.
- **`draw`'s "net-positive" was a coin flip on shuffle-draw.** Lillie's Determination (`me01-119`:
  "Shuffle your hand into your deck. Then, draw 6 cards…") is net-positive only if your hand is
  under 6, yet players call it a draw Supporter. Effects on both players' hands (Judge `me03-076`,
  Iono) had no rule.
- **No tag for flat damage boosts.** `damage-scaling` grows with a count ("N for each…"). Maximum
  Belt (`sv08.5-117`), Defiance Band (`sv01-169`) and an attack's own "does N more damage if…" got
  no tag, or got `damage-scaling` wrongly. The parse prompt already used "tools that boost damage"
  as an example query.
- **No tag for moving Energy.** Energy Switch-style cards had no tag. The parse prompt already
  carried "move energy between my pokemon" as an example.

Decisions:

1. **`prize-manipulation` stays as is**, even though it covers both sides (extra Prizes, denying
   Prizes).
2. **`recoil` is narrowed, not split.** Discarding your own Energy goes untagged; the normalized
   description still says it, so the semantic leg finds it. Abilities count: Dusclops's Cursed
   Blast (Knocks Out itself) is `recoil`.
3. **`energy-movement` covers both sides.** Moving the opponent's Energy carries
   `energy-movement` + `energy-removal`, like "both players switch → `gust` + `switch`".
4. **Both players' hands → `draw` + `hand-disruption`.** Judge and Iono carry both; Lillie's
   Determination carries `draw`.
5. **Attaching from the discard → `acceleration` + `recovery`.**
6. **Preventing "all damage from and effects of attacks" → `damage-prevention` +
   `effect-prevention`.** That wording is the common "next turn" protection (Hoppip, Wiglett).
   Text that says "Damage is not an effect" (Mist Energy, Kakuna) is `effect-prevention` alone.
7. **Merges accept the ranking trade-off.** "Search for energy" tag-matches Nest Ball too, and the
   semantic leg ranks the Energy searchers first. Same trade-off v4 accepted for "exactly one
   Benched Pokémon".
8. **Examples stay single-tag outside the Bench family.** The "carries both" pairs (decisions 3–6)
   don't get v4's `also` treatment. The Bench family needed it because nearly every `multi-target`
   card is also `bench-reach`, so single-tag examples barely exist. Each pair here has plenty of
   cards with one tag alone, and a single-tag example keeps each tag's effect clear. The pairs are
   stated in the enrichment prompt and the confusion-pair notes below instead.
9. **Examples re-checked.** Under the new definitions four v4 examples no longer carried only their
   own tag, and were swapped: Hoppip (prevents damage *and* effects; now Glimmet), Koraidon (only
   discards its own Energy; now Magneton), Dusclops (now `recoil` too; now Iron Valiant ex) and
   Blissey (also moves Energy; now Ancient Booster Energy Capsule). Pidgeot ex and Miracle Headset
   gave way to Earthen Vessel and Energy Retrieval, which show the merged Energy cases. The cards
   the acceptance run checks (Sinistcha, Kyurem, Gengar ex, Lillie's Determination, Judge,
   Maximum Belt, Defiance Band) are kept out of the examples.
10. **Re-tag scope.** The bump re-queues every card (CONTEXT.md: Enrichment identity). Nothing is
    tagged yet, so that costs nothing.

**Prompts.** The glossary alone got most "carries both" rules right in the first live
enrichment run, but tagged Porygon (moves an Energy off the opponent's Active) `energy-movement`
without `energy-removal`. The enrichment prompt now says so in one sentence. The parse prompt gained
one rule naming all three pairs (moving the opponent's Energy, every player's hand reset, attaching
from the discard), after the first v9 parse eval missed the first two; see
[`parse-model-eval-gpt6.md`](parse-model-eval-gpt6.md#after-103-taxonomy-v5-parse_version-v9).
The parse prompt's existing examples ("tools that boost damage", "move energy between my pokemon",
"nothing can damage it next turn") still read right under v5.

**Live check.** `scripts/enrich_sample.py` on 14 cards ($0.023), then 4 after the Porygon note
($0.010), returned the intended tags for every card in the table below except Shaymin and Earthen
Vessel, which are prompt examples and weren't run. It also returned `search` for Energy Search
(`sv01-172`), `acceleration` + `recovery` for Energy Sticker (`sv03.5-159`), and `search` +
`effect-prevention` for Jirachi (`sv04-126`: Stellar Veil stops counters on the Bench). Two
side findings on unchanged tags, left alone: Toedscruel (`sv01-026`) got `damage-scaling` for "80
damage for each heads", and Handheld Fan (`sv06-150`) got `counter-damage` for moving the
attacker's Energy away.

Under v5 the cards from the discussion are tagged:

| Card | v5 tags (from the changed ones) |
|---|---|
| Shaymin `sv10-010` (Flower Curtain) | `damage-prevention` |
| Sinistcha `me05-006` (Hide 'n' Sneak) | `effect-prevention` |
| Hoppip `sv02-001` (Splashing Dodge: damage from and effects of attacks) | `damage-prevention`, `effect-prevention` |
| Kyurem `sv06.5-047` (Trifrost: discards its own Energy) | no `recoil` |
| Dusclops `sv06.5-019` (Cursed Blast: Knocks Out itself) | `recoil` |
| Gengar ex `30th-090` (Fainting Spell: Knocks Out the attacker) | `counter-damage` |
| Lillie's Determination `me01-119` | `draw` |
| Judge `me03-076` | `draw`, `hand-disruption` |
| Maximum Belt `sv08.5-117`, Defiance Band `sv01-169` | `damage-boost` |
| Energy Switch `sv01-173` | `energy-movement` |
| Porygon `sv04-142` (moves the opponent's Energy to their Bench) | `energy-movement`, `energy-removal` |
| Earthen Vessel `sv04-163` | `search` |

## The tags

Families organize this document for humans; they are **not** stored (Q4). Each definition is the
one-liner the enricher and the query-rewriter share. Definitions and examples are mirrored in
`app/enrichment/taxonomy.py` (`TAG_DEFINITIONS`, `TAG_EXAMPLES`), and a test keeps the two in step.
Examples are real Scarlet & Violet–Mega Evolution cards cited by TCGdex id, checked against their
card text; none come from the gold or hero set. Each example carries only the tag it illustrates,
across all of its attacks and Abilities, so the effect is shown in isolation. The exception is
`bench-reach`, `multi-target` and `counter-placement`, whose examples name the others of the
three they also carry (see [`tag-taxonomy-v4.md`](tag-taxonomy-v4.md#what-changed-from-v3)).

### 1 · Card advantage (resources)

| tag | definition | example |
|-----|------------|---------|
| `draw` | Draw cards from your deck, including discarding or shuffling your hand away and drawing a new one. | Dudunsparce (`sv05-129`), Carmine (`sv06-145`) |
| `search` | Fetch a specific card (by name, type, or trait, Energy included) from your deck to hand or Bench. | Nest Ball (`sv01-181`), Earthen Vessel (`sv04-163`) |
| `recovery` | Get cards back from your discard pile — into your hand or deck, onto your Bench, or attached to your Pokémon. | Pal Pad (`sv01-182`), Energy Retrieval (`sv01-171`) |

**Confusion pairs.** `draw` takes cards from the top of your deck; `search` picks a specific card
out of it, Energy included. An effect where both players shuffle their hands away and draw (Judge,
Iono) carries `draw` + `hand-disruption`; one that resets only your own hand (Lillie's
Determination, Carmine) is `draw`. `recovery` is anything back from your discard pile, whatever
the card type and wherever it goes. Attaching Energy from the discard carries `acceleration` +
`recovery`.

### 2 · Energy

| tag | definition | example |
|-----|------------|---------|
| `acceleration` | Attach Energy beyond your one normal manual attachment per turn. | Baxcalibur (`sv02-060`), Barbaracle (`me03-043`) |
| `energy-movement` | Move Energy from one Pokémon to another, on either player's side. | Poppy (`sv03-193`), Dewgong (`me03-019`) |
| `energy-removal` | The *opponent's* Pokémon loses Energy: discard it, or move it off. | Enhanced Hammer (`sv06-148`), Crushing Hammer (`sv01-168`) |

**Confusion pairs.** `energy-movement`, `energy-removal` and `acceleration` all change where Energy
sits. Moving Energy between Pokémon is not attaching beyond the one per turn, so it is
`energy-movement`, not `acceleration`; attaching from your hand, deck or discard is `acceleration`.
Moving your own Energy is `energy-movement` alone. Moving the opponent's Energy off their Active
Pokémon carries `energy-movement` + `energy-removal`, since their Pokémon loses it. Discarding the
opponent's Energy is `energy-removal` alone, and discarding your own goes untagged.

### 3 · Offense — damage shaping

| tag | definition | example |
|-----|------------|---------|
| `bench-reach` | An attack or Ability can deal damage to, or put damage counters on, one or more of the opponent's *Benched* Pokémon. | Golbat (`sv03.5-042`), Elekid (`sv04-059`) |
| `multi-target` | One attack or Ability use can deal damage to, or put damage counters on, more than one of the opponent's Pokémon (choosing a target several times counts, even if every hit lands on one). | Lapras (`sv03-045`, also `bench-reach`), Regice (`sv09-042`, also `bench-reach`) |
| `damage-scaling` | Attack damage grows with a game-state count — Energy attached, damage counters, cards discarded. | Chandelure (`sv03-038`), Drampa (`sv03-161`) |
| `damage-boost` | Make attacks do a fixed amount more damage — from a Tool, Ability, Stadium, Item, Supporter or Energy, or an attack's own conditional bonus ("does 100 more damage if…"). A per-count increase is `damage-scaling`. | Vitality Band (`sv01-197`), Greedent (`sv01-152`) |
| `recoil` | An attack or Ability does damage to, or Knocks Out, *your own* Pokémon. | Primeape (`sv01-108`), Magneton (`sv01-064`) |
| `counter-placement` | Put damage counters directly on the opponent's Pokémon rather than dealing damage, so Weakness, Resistance and damage-reduction don't apply. Retaliation when your Pokémon is hit is `counter-damage`. | Drifblim (`sv01-090`, also `bench-reach`, `multi-target`), Iron Valiant ex (`sv04-089`, also `bench-reach`) |

**Confusion pairs.** `bench-reach`, `multi-target` and `counter-placement` each answer one
question, and a card carries every one that applies. `bench-reach` is about *where*: the effect can
land on a Benched Pokémon, by damage or by counters. `multi-target` is about *how many*: one use
can hit more than one of the opponent's Pokémon. `counter-placement` is about *how*: counters
instead of damage, so it gets past Weakness, Resistance, damage-reduction and damage prevention.
Dragapult ex's Phantom Dive (damage to the Active, counters spread over the Bench) carries all
three; Golbat's Skill Dive (40 damage to 1 of the opponent's Pokémon) carries only `bench-reach`.
`counter-damage` is hitting back when your Pokémon is hit, and never one of these three. Dragging a
Benched Pokémon up before hitting it is `gust`, not `bench-reach`: the hit lands on the new Active.

`damage-scaling` and `damage-boost` both add damage. `damage-scaling` grows with a count ("50 more
damage for each Energy attached", Chandelure); `damage-boost` is a fixed extra amount, on a
condition or not (Vitality Band's 10 more; Greedent's "80 more damage" if it has a Tool attached).
`recoil` is only your own Pokémon taking damage or being Knocked Out (Primeape's Raging Punch,
Magneton's Explosion, Dusclops's Cursed Blast); discarding your own Energy is not `recoil`.

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
| `condition-heal` | Remove Special Conditions from your Pokémon. | Ancient Booster Energy Capsule (`sv04-159`), Therapeutic Energy (`sv02-193`) |
| `damage-reduction` | Reduce the damage your Pokémon take from the opponent's attacks. | Rock Chestplate (`sv01-192`), Stonjourner (`sv01-121`) |
| `damage-prevention` | Prevent the damage the opponent's attacks do to your Pokémon, under a condition (a Benched Pokémon, next turn). | Shaymin (`sv10-010`), Glimmet (`sv03-121`) |
| `effect-prevention` | Prevent the effects of the opponent's attacks or Abilities on your Pokémon, including damage counters they place. | Mist Energy (`sv05-161`), Kakuna (`sv03.5-014`) |
| `counter-damage` | When your Pokémon is hit by an attack, punish the Attacking Pokémon — damage, damage counters, or a Knock Out. | Rocky Helmet (`sv01-193`), Cacturne (`sv01-006`) |

**Confusion pairs.** `damage-prevention`, `effect-prevention` and `counter-placement`: damage
counters get past damage prevention but not effect prevention. Shaymin's Flower Curtain stops
attack damage to the Bench, but not Dragapult ex's counters; an effect-prevention Ability that
covers the Bench stops both the counters and any other effect. Text that prevents "all damage from
and effects of attacks" (Hoppip's Splashing Dodge) carries both tags; text that adds "Damage is not
an effect" (Mist Energy) is `effect-prevention` alone.

`stall` and `damage-prevention`: "the Defending Pokémon can't attack" targets the opponent and is
`stall`; "prevent all damage done to this Pokémon" protects yours and is `damage-prevention`.
`damage-reduction` takes some damage off; `damage-prevention` stops all of it under its condition.
`counter-damage` punishes the attacker after your Pokémon is hit, by damage, counters or a Knock
Out.

### 7 · Prize & win condition

| tag | definition | example |
|-----|------------|---------|
| `prize-manipulation` | Change how Prizes are taken — extra Prizes on KO, or denying the opponent Prizes. | Iron Hands ex (`sv04-070`), Legacy Energy (`sv06-167`) |
| `stall` | Stop the opponent from attacking or taking their turn — the Defending Pokémon can't attack, they skip a turn. | Lickitung (`sv03.5-108`), Frosmoth (`sv05-046`) |

## Enum (flat, for the enricher schema)

```
draw, search, recovery,
acceleration, energy-movement, energy-removal,
bench-reach, multi-target, damage-scaling, damage-boost, recoil, counter-placement,
hand-disruption, mill, ability-lock, item-lock, special-condition, movement-lock,
gust, switch, retreat-reduction, evolution-accel,
healing, condition-heal, damage-reduction, damage-prevention, effect-prevention, counter-damage,
prize-manipulation, stall
```

Plus the reserved out-of-band field `suggested_new_tag` (free text, never part of the enum).

## Downstream consumers

- **#5 — offline enrichment pipeline**: tags cards from this enum; carries `taxonomy_version` (`v5`).
- **#8 — query parse & concept rewrite**: rewrites use this vocabulary/definitions so queries
  align with both the tag layer and the embedded descriptions.
- **Later versions**: `suggested_new_tag` + fall-through query logging (fogged on the map).
