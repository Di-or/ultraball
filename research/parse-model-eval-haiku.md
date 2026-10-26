# Parse model eval: GPT-5.6 Luna vs Claude Haiku 5.5, low and medium effort

**Follows:** [#85: Compare parse models and reasoning efforts](https://github.com/Di-or/ultraball/issues/85) ([first run](parse-model-eval.md))
**Date:** 2026-10-25, measured against `main` at `31a9451` (`PARSE_VERSION` v6, 29-tag v3 taxonomy, set-id resolution from #90)
**Rerun:** `uv run python -m scripts.parse_model_eval` (needs `OPENAI_API_KEY`, `CLAUDE_API_KEY`, and `CLAUDE_WORKSPACE_ID` for a key not scoped to a workspace). `--report` re-renders the tables below from `parse-model-eval-haiku-raw.json` without calling the API.

This file holds measurements only. It does not choose the parse model or change the 4s timeout.

## What changed since the first run

- **Configurations:** Luna and Claude Haiku 5.5, each at `low` and `medium` effort (`medium` is both models' default). gpt-5-mini and Luna `none` are dropped.
- **Prompt:** main's parse prompt now lists the catalog's sets, and `set_id` is an enum of their ids (#90). The eval builds the prompt from a fixed SV-to-Mega set list checked in as `scripts/parse_eval_sets.json`: 22 sets from SVI (sv01) to PBL (me05), with ids, PTCGL codes and names from TCGdex. Input grew from ~1,430 to 1,989 tokens per Luna call.
- **Claude request:** the same system prompt and schema through the Messages API. Structured output goes through `output_config.format`, the effort through `output_config.effort`, and the system prompt is marked `cache_control: ephemeral`. Thinking is left at Haiku 5.5's default (adaptive). Anthropic's schema validator rejects the production schema's nullable enums (`"type": ["string", "null"]` with `null` in the enum), so the script rewrites each one to the equivalent `anyOf: [<type>, {"type": "null"}]`. The values the schema allows are unchanged. Haiku reports 4,484 input tokens per call against Luna's 1,989 for the same prompt; most of the gap is how Anthropic counts the structured-output schema and its tokenizer. All but ~20 of them are cached.
- **Queries:** 47, up from 25.
  - **30 standard.** The first run's 25, with "retreat for free" now expecting `retreat-reduction` (v3), plus the #85 follow-ups: "pokemon with no retreat cost" (a `retreat` ≤ 0 filter, no tag), "switch my active with my bench" and "switch out even if they block retreating" (`switch`), "TWM supporters" (`sv06` by PTCGL code) and "pokemon from Surging Sparks" (`sv08` by name).
  - **17 hard**, marked `"difficulty": "hard"` and scored in their own row so they don't move the standard numbers. They target negation the positive-only filters can't express ("non-ex pokemon that heal"), set names that collide with other words ("mega pokemon from Phantasmal Flames", where a "Mega Evolution" set also exists; "black bolt lightning pokemon"; "151 pokemon with free retreat"), stacked numeric filters, slang ("turbo evolve my pokemon"), close tag pairs (counter-damage vs counter-placement, stall vs special-condition, movement-lock vs gust) and multi-tag queries.
- **Cost:** Haiku 5.5 at $0.10 / $0.01 / $0.50 per 1M uncached input / cached input / output tokens, with cache writes at 1.25× the input rate. Luna's rates are unchanged ($0.20 / $0.02 / $1.20).

Everything else (3 runs per query after one warm-up per configuration, 60s timeout, fresh client per call, scoring) is as in the [first run](parse-model-eval.md#method). Calls came from one Windows machine on a home connection, in one session, with the four configurations running side by side.

## Trade-offs

**Latency.**
- Haiku 5.5 `low` is the fastest: 1.41s median on standard queries and 1.59s on hard ones, with every call within 4s. 83% of standard calls and 94% of hard calls finished within 2s.
- Haiku 5.5 `medium` has the same standard median (1.43s) but a longer tail (p95 3.52s; 98% within 4s). On hard queries it thinks more (128 reasoning tokens on average, against 46 on standard ones) and its median rises to 2.07s.
- Luna `low` matches the first run (1.87s median, p95 2.36s), even with the longer prompt.
- Luna `medium` is the slowest, especially on hard queries: 2.59s median, p95 3.93s, 76% within 3s and 96% within 4s.
- So everything fits today's 4s timeout at 96% or better, but only Haiku `low` and Luna `low` would also fit a 3s one on both query sets (96–99%).

**Quality, standard queries.**
- Luna `medium` is exact on filters (100%) with tag precision 1.00. Luna `low` is at 97% / 1.00.
- Both Haiku efforts are at 93% filters. The misses are mostly `category: Pokemon` added where the expectations leave it out ("get pokemon back from the discard pile", "attacker that does more damage for each energy attached"); see the note on expectations below.
- Haiku `low` over-tagged #80's noisy query "stadium that punishes ex" on 2 of 3 runs (`counter-damage`, `damage-scaling`), and both Haiku efforts sometimes added `snipe` to "put damage counters on their bench". Haiku `medium` once returned no tag for "bring up their bench".
- Recall is 0.94–0.96 everywhere. The miss shared by every configuration is "hit their bench for damage", where all answered `snipe` without `spread`, as in the first run.
- "retreat for free" now comes back as `retreat-reduction` with no filter from every configuration, and the three set queries (by name and by PTCGL code) resolve to the right ids on every run. The no-retreat-cost and `switch` follow-ups are also correct everywhere.

**Quality, hard queries.**
- The hard set is easier than intended: every configuration has recall 1.00, and 14 of the 17 queries were answered correctly by all four configurations on every run.
- Luna `medium` is perfect (100% filters, 1.00 / 1.00). Luna `low` and Haiku `medium` are close (98% filters).
- Haiku `low` is the weakest at 90% filters and precision 0.92. On "151 pokemon with free retreat" it dropped the `sv03.5` set on 2 of 3 runs; on "turbo evolve my pokemon" it added a `category` filter, once `Item`; and it added `damage-reduction` to "pokemon that can't be hurt by ex".
- Luna `low` also slipped once on "151 pokemon with free retreat", treating "free retreat" as `retreat-reduction` instead of the printed stat.
- No configuration put an `ex` filter on the negation traps ("non-ex pokemon that heal", "pokemon that can't be hurt by ex"), and every configuration resolved both set-name collisions on every run. They don't separate the models today, but they guard against regressions.

**Cost.**
- Per 1,000 standard queries: Haiku `low` $0.135, Haiku `medium` $0.155, Luna `low` $0.172, Luna `medium` $0.195. Hard queries cost 4–28% more, mostly from extra reasoning at `medium`.
- Haiku sends more than twice as many input tokens, but at half Luna's rates, all cached, and with output at $0.50 against $1.20, it still comes out cheaper.
- The whole run (568 calls) cost $0.10.

**Note on expectations.** Some filter "misses" are arguable:
- `category: Pokemon` for "attacker that does more damage for each energy attached" is defensible, since an attacker is a Pokémon.
- `{"category": "Pokemon"}` for "get pokemon back from the discard pile" and "turbo evolve my pokemon" is wrong: those queries describe what the card does to your Pokémon, not the card itself, and the filter would hide Trainer cards like Pal Pad or Rare Candy.
- Haiku's `attack_cost: {lte: 1}` for "a 1-energy attack" is accepted.
- The maintainer may want to accept the first case before reading too much into the filter gap between Luna and Haiku.

## Results

Standard: 30 queries. Hard: 17 queries, scored separately.

| Configuration | Cases | Calls | Errors | Median | p95 | ≤2s | ≤3s | ≤4s | ≤6s | ≤8s | Reasoning tok | Completion tok | Cached | Filters exact | Tag P | Tag R | $ / 1k queries |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `gpt-5.6-luna / low` | standard | 90 | 0 | 1.87s | 2.36s | 71% | 98% | 98% | 99% | 100% | 4 | 109 | 100% | 97% | 1.00 | 0.96 | $0.172 |
| `gpt-5.6-luna / low` | hard | 51 | 0 | 1.92s | 2.58s | 65% | 96% | 100% | 100% | 100% | 16 | 127 | 100% | 98% | 0.98 | 1.00 | $0.193 |
| `gpt-5.6-luna / medium` | standard | 90 | 0 | 2.20s | 3.08s | 34% | 93% | 100% | 100% | 100% | 22 | 129 | 100% | 100% | 1.00 | 0.96 | $0.195 |
| `gpt-5.6-luna / medium` | hard | 51 | 0 | 2.59s | 3.93s | 8% | 76% | 96% | 98% | 100% | 54 | 168 | 100% | 100% | 1.00 | 1.00 | $0.243 |
| `claude-haiku-5-5 / low` | standard | 90 | 0 | 1.41s | 2.42s | 83% | 99% | 100% | 100% | 100% | 6 | 177 | 100% | 93% | 0.96 | 0.96 | $0.135 |
| `claude-haiku-5-5 / low` | hard | 51 | 0 | 1.59s | 2.30s | 94% | 98% | 100% | 100% | 100% | 4 | 187 | 100% | 90% | 0.92 | 1.00 | $0.140 |
| `claude-haiku-5-5 / medium` | standard | 90 | 0 | 1.43s | 3.52s | 82% | 91% | 98% | 99% | 99% | 46 | 217 | 100% | 93% | 0.98 | 0.94 | $0.155 |
| `claude-haiku-5-5 / medium` | hard | 51 | 0 | 2.07s | 3.10s | 47% | 94% | 100% | 100% | 100% | 128 | 306 | 100% | 98% | 1.00 | 1.00 | $0.199 |

Whole run (568 calls including warm-ups, 0 failed): 1,836,406 input tokens (1,826,064 cached), 97,504 output tokens (17,180 of them reasoning), **$0.10**.

### `concept_rewritten` samples (run 1)

**energy accel**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low` | Attach extra Energy beyond the one-per-turn manual attachment. |
| `gpt-5.6-luna / medium` | Attach extra Energy from your hand or deck beyond the one-per-turn attachment. |
| `claude-haiku-5-5 / low` | attach extra Energy from your hand or deck beyond the one-per-turn attachment |
| `claude-haiku-5-5 / medium` | attach extra Energy from your hand or deck beyond the one-per-turn attachment |

**stall the opponent**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low` | waste the opponent's turn or stall the game without trading KOs, such as by blocking attacks or forcing skips |
| `gpt-5.6-luna / medium` | waste the opponent's turn or stall the game without trading KOs |
| `claude-haiku-5-5 / low` | waste the opponent's turn or stall the game without trading knockouts by blocking attacks, forcing skips, or running the clock |
| `claude-haiku-5-5 / medium` | waste the opponent's turn or stall the game without trading knockouts, blocking attacks, forcing skips, or running the clock |

**put damage counters on their bench**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low` | put damage counters directly on the opponent's Benched Pokémon |
| `gpt-5.6-luna / medium` | Place damage counters directly on one or more of the opponent's Benched Pokémon |
| `claude-haiku-5-5 / low` | place damage counters on the opponent's Benched Pokémon, not dealing damage, so Weakness and Resistance do not apply |
| `claude-haiku-5-5 / medium` | put damage counters on the opponent's Benched Pokémon rather than dealing damage to the Active Pokémon |

**stadium that punishes ex**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low` | applies a negative effect to Pokémon ex |
| `gpt-5.6-luna / medium` | a Stadium card with a detrimental effect involving Pokémon ex |
| `claude-haiku-5-5 / low` | Stadium that deals extra damage to or otherwise penalizes the opponent's Pokémon ex while it is in play |
| `claude-haiku-5-5 / medium` | Stadium card whose effect adds extra damage or extra Prize cards when the opponent's Pokémon ex is Knocked Out or attacked |

**punish them for attacking me**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low` | deal damage back to the opponent's Pokémon when they attack your Pokémon |
| `gpt-5.6-luna / medium` | deal damage back to the opponent's attacking Pokémon when your Pokémon is hit by an attack |
| `claude-haiku-5-5 / low` | when this Pokémon is damaged by an opponent's attack, deal damage back to the attacking Pokémon |
| `claude-haiku-5-5 / medium` | deal damage back to the attacking Pokémon when your Pokémon is hit by an opponent's attack |

### Per-query disagreements

**get pokemon back from the discard pile** (expected `{}` · recovery)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{}` · recovery |
| `gpt-5.6-luna / medium` | `{}` · recovery |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon"}` · recovery |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon"}` · recovery |

**attacker that does more damage for each energy attached** (expected `{}` · damage-scaling)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon"}` · damage-scaling<br>`{}` · damage-scaling |
| `gpt-5.6-luna / medium` | `{}` · damage-scaling |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon"}` · damage-scaling |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon"}` · damage-scaling |

**items that search for a pokemon** (expected `{"trainer_type": "Item"}` · search)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Trainer", "trainer_type": "Item"}` · search<br>`{"category": "Trainer"}` · search |
| `gpt-5.6-luna / medium` | `{"category": "Trainer", "trainer_type": "Item"}` · search<br>`{"trainer_type": "Item"}` · search |
| `claude-haiku-5-5 / low` | `{"category": "Trainer", "trainer_type": "Item"}` · search |
| `claude-haiku-5-5 / medium` | `{"category": "Trainer", "trainer_type": "Item"}` · search |

**bring up their bench** (expected `{}` · gust)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{}` · gust |
| `gpt-5.6-luna / medium` | `{}` · gust |
| `claude-haiku-5-5 / low` | `{}` · gust |
| `claude-haiku-5-5 / medium` | `{}` · gust<br>`{}` · (no tags) |

**put damage counters on their bench** (expected `{}` · counter-placement)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{}` · counter-placement |
| `gpt-5.6-luna / medium` | `{}` · counter-placement |
| `claude-haiku-5-5 / low` | `{}` · counter-placement, snipe<br>`{}` · counter-placement |
| `claude-haiku-5-5 / medium` | `{}` · counter-placement, snipe<br>`{}` · counter-placement |

**stadium that punishes ex** (expected `{"trainer_type": "Stadium"}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Trainer", "trainer_type": "Stadium"}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"category": "Trainer", "trainer_type": "Stadium"}` · (no tags) |
| `claude-haiku-5-5 / low` | `{"category": "Trainer", "trainer_type": "Stadium"}` · counter-damage<br>`{"category": "Trainer", "trainer_type": "Stadium"}` · damage-scaling<br>`{"category": "Trainer", "trainer_type": "Stadium"}` · (no tags) |
| `claude-haiku-5-5 / medium` | `{"category": "Trainer", "trainer_type": "Stadium"}` · (no tags) |

**big hp basic** (expected `{"stage": "Basic"}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon", "stage": "Basic"}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon", "stage": "Basic"}` · (no tags)<br>`{"stage": "Basic"}` · (no tags) |
| `claude-haiku-5-5 / low` | `{"stage": "Basic"}` · (no tags) |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon", "stage": "Basic"}` · (no tags) |

**pokemon that can't be hurt by ex** — hard (expected `{"category": "Pokemon"}` · damage-prevention)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon"}` · damage-prevention |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon"}` · damage-prevention |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon"}` · damage-prevention, damage-reduction |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon"}` · damage-prevention |

**151 pokemon with free retreat** — hard (expected `{"category": "Pokemon", "set_id": "sv03.5", "retreat": {"lte": 0}}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon", "retreat": {"lte": 0}, "set_id": "sv03.5"}` · (no tags)<br>`{"category": "Pokemon", "set_id": "sv03.5"}` · retreat-reduction |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}, "set_id": "sv03.5"}` · (no tags) |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}, "set_id": "sv03.5"}` · (no tags)<br>`{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}}` · retreat-reduction<br>`{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}}` · (no tags) |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}, "set_id": "sv03.5"}` · (no tags) |

**stage 2 with 300+ hp and a 1-energy attack** — hard (expected `{"stage": "Stage 2", "hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon", "hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}, "stage": "Stage 2"}` · (no tags)<br>`{"hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}, "stage": "Stage 2"}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}, "stage": "Stage 2"}` · (no tags) |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon", "hp": {"gte": 300}, "attack_cost": {"lte": 1}, "stage": "Stage 2"}` · (no tags) |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon", "hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}, "stage": "Stage 2"}` · (no tags)<br>`{"hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}, "stage": "Stage 2"}` · (no tags) |

**turbo evolve my pokemon** — hard (expected `{}` · evolution-accel)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{}` · evolution-accel |
| `gpt-5.6-luna / medium` | `{}` · evolution-accel |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon"}` · evolution-accel<br>`{"category": "Trainer", "trainer_type": "Item"}` · evolution-accel |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon"}` · evolution-accel<br>`{}` · evolution-accel |

