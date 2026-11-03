# Functional-Tag Taxonomy — v4

> v3 ([`tag-taxonomy-v3.md`](tag-taxonomy-v3.md)) with `snipe` and `spread` replaced by
> `bench-reach` and `multi-target`, and `counter-placement` reworded, from
> [issue #101](https://github.com/Di-or/ultraball/issues/101). Every other tag and definition is
> unchanged from v3. See [What changed from v3](#what-changed-from-v3).
> v1 and v2 are [`tag-taxonomy-v1.md`](tag-taxonomy-v1.md) and [`tag-taxonomy-v2.md`](tag-taxonomy-v2.md).

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
| Q6 | Tag count | **Ship 27.** Every tag maps to a real, queryable archetype; `suggested_new_tag` grows the rest from real data. v2 added `counter-placement`; v3 added `retreat-reduction`; v4 swaps `snipe`/`spread` for `bench-reach`/`multi-target`. |

## What changed from v3

v4 replaces `snipe` and `spread` with `bench-reach` and `multi-target`, and drops the
Active/Bench wording from `counter-placement`. The tag count stays at 29. No other tag or
definition changed.

In v3 three tags mixed two questions: *how* a card puts damage on the opponent's Pokémon and
*where or how many* it hits. `snipe` ("a chosen *Benched* Pokémon") and `spread` ("multiple of
the opponent's Pokémon") were about damage plus a target count; `counter-placement` was about
counters alone and said nothing about the count. That left cards and queries the tags couldn't
express:

- Dragapult ex (`sv06-130`, Phantom Dive) deals damage to the Active and puts counters on the
  Bench. The first live enrichment run (#77, #100) tagged it `counter-placement, spread`. Under v3
  the strict answer was `counter-placement` only, though a player would say it hits the Bench and
  hits several Pokémon.
- Sinistcha (`me05-006`, Matcha Spin: 4 counters on each of the opponent's Pokémon) and Gengar ex
  (`30th-090`, Chaotic Pain: 13 counters on 1 of the opponent's Pokémon) got the same tag, so
  "damage all of their Pokémon" couldn't find Sinistcha without also finding Gengar ex.
- "Hit their Bench" should find snipers, spreaders and counter placers alike: counters put damage
  on the Bench too, they just get past what blocks attack damage, such as Shaymin. v3 could only
  get there by having the parser emit all three tags, and a parse eval of that rule (the unmerged
  `parse-bench-tags` branch) showed it leaking onto non-Bench queries.

Decisions:

- **One question per tag.** `bench-reach`: can it hit a Benched Pokémon? `multi-target`: can one
  use hit more than one Pokémon? `counter-placement`: does it use counters instead of damage? The
  three combine freely.
- **`snipe` and `spread` are removed, not redefined.** Players' "snipe" usually means targeted
  damage to one Benched Pokémon, and a re-meant word would invite the same confusion. The parser
  maps the slang ("snipe", "spread") onto the new tags.
- **Abilities count**, not just attacks: a Dusclops-style Ability that places counters qualifies.
- **Repeated choice is `multi-target`.** Arboliva ex (`sv10-023`, Oil Salvo: 20 damage to a chosen
  Pokémon, 6 times) counts even though all six hits may land on one Pokémon.
- **Example rule for this family.** Elsewhere each example carries only its own tag. That can't
  hold here: nearly anything `multi-target` is also `bench-reach`, since there is only one Active.
  Examples for these three tags instead show the tag's effect clearly and name which of the other
  two they also carry. In `app/enrichment/taxonomy.py` that is `TagExample.also`, and the prompt
  glossary shows it ("Lapras (also bench-reach)"). Every other tag keeps the single-tag rule.
- **Known trade-off, accepted.** Tags are positive only, so "hits exactly one Benched Pokémon"
  can't be expressed as a tag. A classic snipe query gets `bench-reach`, and a card that spreads
  small damage to everyone matches it too. The normalized description still separates "100 damage
  to 1 Benched Pokémon" from "10 to each", so the semantic leg ranks them.
- **Prompts.** The enrichment prompt drops v3's "placing damage counters is not dealing damage …
  not `spread`" rule and says the three tags combine freely. The parse prompt replaces both v3
  Bench rules: a plain Bench query is `bench-reach`, hitting several or all is `multi-target`, and
  naming damage counters adds `counter-placement`.
- **Re-tag scope.** The bump re-queues every card (CONTEXT.md: Enrichment identity). Nothing is
  tagged yet, so that costs nothing.

Under v4 the cards from the discussion are tagged:

| Card | `bench-reach` | `multi-target` | `counter-placement` |
|---|---|---|---|
| Dragapult ex `sv06-130` (Phantom Dive) | ✓ | ✓ | ✓ |
| Sinistcha `me05-006` (Matcha Spin) | ✓ | ✓ | ✓ |
| Gengar ex `30th-090` (Chaotic Pain) | ✓ | | ✓ |
| Arboliva ex `sv10-023` (Oil Salvo) | ✓ | ✓ | |
| Kyurem `sv06.5-047` (Trifrost: 110 damage to 3 of their Pokémon) | ✓ | ✓ | |
| Golbat `sv03.5-042` (Skill Dive: 40 damage to 1 of their Pokémon) | ✓ | | |

## The tags

Families organize this document for humans; they are **not** stored (Q4). Each definition is the
one-liner the enricher and the query-rewriter share. Definitions and examples are mirrored in
`app/enrichment/taxonomy.py` (`TAG_DEFINITIONS`, `TAG_EXAMPLES`), and a test keeps the two in step.
Examples are real Scarlet & Violet–Mega Evolution cards cited by TCGdex id, checked against their
card text; none come from the gold or hero set. Each example carries only the tag it illustrates,
across all of its attacks and Abilities, so the effect is shown in isolation. The exception is
`bench-reach`, `multi-target` and `counter-placement`, whose examples name the others of the
three they also carry (see [What changed from v3](#what-changed-from-v3)).

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
| `bench-reach` | An attack or Ability can deal damage to, or put damage counters on, one or more of the opponent's *Benched* Pokémon. | Golbat (`sv03.5-042`), Elekid (`sv04-059`) |
| `multi-target` | One attack or Ability use can deal damage to, or put damage counters on, more than one of the opponent's Pokémon (choosing a target several times counts, even if every hit lands on one). | Lapras (`sv03-045`, also `bench-reach`), Regice (`sv09-042`, also `bench-reach`) |
| `damage-scaling` | Attack damage grows with a game-state count — Energy attached, damage counters, cards discarded. | Chandelure (`sv03-038`), Drampa (`sv03-161`) |
| `recoil` | Attack costs damage to, or discards Energy from, *your own* Pokémon. | Koraidon (`sv01-124`), Primeape (`sv01-108`) |
| `counter-placement` | Put damage counters directly on the opponent's Pokémon rather than dealing damage, so Weakness, Resistance and damage-reduction don't apply. Retaliation when your Pokémon is hit is `counter-damage`. | Drifblim (`sv01-090`, also `bench-reach`, `multi-target`), Dusclops (`sv06.5-019`, also `bench-reach`) |

**Confusion pairs.** `bench-reach`, `multi-target` and `counter-placement` each answer one
question, and a card carries every one that applies. `bench-reach` is about *where*: the effect can
land on a Benched Pokémon, by damage or by counters. `multi-target` is about *how many*: one use
can hit more than one of the opponent's Pokémon. `counter-placement` is about *how*: counters
instead of damage, so it gets past Weakness, Resistance, damage-reduction and Bench protection
against attack damage. Dragapult ex's Phantom Dive (damage to the Active, counters spread over the
Bench) carries all three; Golbat's Skill Dive (40 damage to 1 of the opponent's Pokémon) carries
only `bench-reach`. `counter-damage` is hitting back when your Pokémon is hit, whether by damage or
counters, and never one of these three. And dragging a Benched Pokémon up before hitting it is
`gust`, not `bench-reach`: the hit lands on the new Active.

Lapras's Hail (10 damage to each of the opponent's Pokémon) and Regice's Blizzard (also 10 to
each Benched Pokémon) show `multi-target`; both reach the Bench. Drifblim's Curse Spreading (8
counters in any way you like) shows the attack form of `counter-placement` and Dusclops's Cursed
Blast (5 counters on 1 of the opponent's Pokémon) the Ability form.

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
bench-reach, multi-target, damage-scaling, recoil, counter-placement,
hand-disruption, mill, ability-lock, item-lock, special-condition, movement-lock,
gust, switch, retreat-reduction, evolution-accel,
healing, condition-heal, damage-reduction, damage-prevention, counter-damage,
prize-manipulation, stall
```

Plus the reserved out-of-band field `suggested_new_tag` (free text, never part of the enum).

## Downstream consumers

- **#5 — offline enrichment pipeline**: tags cards from this enum; carries `taxonomy_version` (`v4`).
- **#8 — query parse & concept rewrite**: rewrites use this vocabulary/definitions so queries
  align with both the tag layer and the embedded descriptions.
- **Later versions**: `suggested_new_tag` + fall-through query logging (fogged on the map).
