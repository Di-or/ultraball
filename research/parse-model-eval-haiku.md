# Parse model eval: GPT-5.6 Luna vs Claude Haiku 5.5, low and medium effort

**Follows:** [#85: Compare parse models and reasoning efforts](https://github.com/Di-or/ultraball/issues/85) ([first run](parse-model-eval.md))
**Date:** 2026-10-25, measured against `main` at `31a9451` (`PARSE_VERSION` v6, 29-tag v3 taxonomy, set-id resolution from #90)
**Rerun:** `uv run python -m scripts.parse_model_eval` for the production prompt and `--prompt rules` for the candidate rules below (needs `OPENAI_API_KEY`, `CLAUDE_API_KEY`, and `CLAUDE_WORKSPACE_ID` for a key not scoped to a workspace). `--report` (with the same `--prompt`) re-renders the tables from `parse-model-eval-haiku-raw.json` or `parse-model-eval-haiku-rules-raw.json` without calling the API.

This file holds measurements only. It does not choose the parse model or change the 4s timeout.

## What changed since the first run

- **Configurations:** Luna and Claude Haiku 5.5, each at `low` and `medium` effort (`medium` is both models' default). gpt-5-mini and Luna `none` are dropped.
- **Prompt:** main's parse prompt now lists the catalog's sets, and `set_id` is an enum of their ids (#90). The eval builds the prompt from a fixed SV-to-Mega set list checked in as `scripts/parse_eval_sets.json`: 22 sets from SVI (sv01) to PBL (me05), with ids, PTCGL codes and names from TCGdex. Input grew from ~1,430 to 1,989 tokens per Luna call.
- **Claude request:** the same system prompt and schema through the Messages API. Structured output goes through `output_config.format`, the effort through `output_config.effort`, and the system prompt is marked `cache_control: ephemeral`. Thinking is left at Haiku 5.5's default (adaptive). Anthropic's schema validator rejects the production schema's nullable enums (`"type": ["string", "null"]` with `null` in the enum), so the script rewrites each one to the equivalent `anyOf: [<type>, {"type": "null"}]`; the values the schema allows are unchanged. Haiku reports 4,484 input tokens per call against Luna's 1,989 for the same prompt, mostly from how Anthropic counts the structured-output schema and from its tokenizer. All but ~20 of them are cached.
- **Queries:** 89, up from 25: 44 standard and 45 hard. Queries marked `"difficulty": "hard"` are scored in their own rows so they don't move the standard numbers.
  - **Standard** adds to the first run's 25: the #85 follow-ups ("retreat for free" now expects `retreat-reduction`; "pokemon with no retreat cost", two `switch` queries, sets by PTCGL code and by name) and 14 more single-filter and single-tag queries (types, stages, Special Energy, Tools, retreat and attack-cost ranges, set names, and one tag each for search, special conditions, hand disruption, mill, energy recovery and condition healing).
  - **Hard** covers:
    - stacked filters with a tag ("lightning pokemon ex with 1 retreat that snipe", "stage 2 grass pokemon over 150 hp from Temporal Forces");
    - category traps, where a Pokémon or Energy is what the effect acts on rather than the card searched for ("put a pokemon from my deck onto the bench", "basic energy acceleration from the discard", "turbo evolve my pokemon");
    - negation the positive-only filters can't express ("non-ex pokemon that heal", "items that are not ace spec");
    - set names that collide ("mega pokemon from Phantasmal Flames", "151 pokemon with free retreat");
    - restraint, where no number or tag is stated ("cheap attackers with big damage", "stop my opponent from playing supporters");
    - card names and slang ("cards like Boss's Orders", "bench barrier", "turbo evolve");
    - close tag pairs and multi-tag queries.
  - "attacker that does more damage for each energy attached" accepts `category: Pokemon`, since an attacker is a Pokémon.
- **Cost:** Haiku 5.5 at $0.10 / $0.01 / $0.50 per 1M uncached input / cached input / output tokens, with cache writes at 1.25× the input rate. Luna's rates are unchanged ($0.20 / $0.02 / $1.20).

Everything else (3 runs per query after one warm-up per configuration, 60s timeout, fresh client per call, scoring) is as in the [first run](parse-model-eval.md#method). Calls came from one Windows machine on a home connection. The production-prompt and rules runs ran at the same time, so all eight configurations were measured side by side: 2,144 calls, none failed, $0.41 in total.

### Candidate parse rules (`--prompt rules`)

Four rules, appended after the production instructions (`_RULES` in `scripts/parse_model_eval.py`). Production is unchanged; adopting them is a `parse_client.py` change that bumps `PARSE_VERSION`.

1. **Category:** fill `category` only when the query says what kind of card it wants. A Pokémon or Energy the effect acts on isn't the card's category.
2. **Snipe and spread:** damage to the opponent's Bench without saying one Pokémon or several gets both `snipe` and `spread`.
3. **No guessed mechanisms:** tag only effects the query describes. A goal without an effect ("good against big attackers") gets no tags; a described effect still gets its tag.
4. **Counters aren't damage:** don't pair `counter-placement` with `snipe` or `spread`.

The rules' examples deliberately avoid the eval queries' wording. A first draft quoted near-copies of eval queries and looked perfect for Haiku, which said more about the examples than the rules; it was rewritten before these runs.

## Summary

| Configuration | Prompt | Standard: filters / tag P / tag R | Hard: filters / tag P / tag R | Median std / hard | p95 hard | Within 3s, hard | Queries fully right (std, hard) | Wrong on every run | $ / 1k std |
| --- | --- | --- | --- | --- | --- | ---: | --- | ---: | ---: |
| Luna `low` | production | 98% / 1.00 / 0.97 | 97% / 0.97 / 1.00 | 1.73s / 2.12s | 2.99s | 96% | 41/44, 41/45 | 1 | $0.169 |
| Luna `low` | + rules | 99% / 1.00 / 1.00 | 97% / 0.97 / 1.00 | 1.73s / 2.00s | 2.96s | 96% | 43/44, 41/45 | 0 | $0.176 |
| Luna `medium` | production | 98% / 0.99 / 0.97 | 98% / 1.00 / 0.99 | 2.03s / 2.47s | 3.73s | 79% | 40/44, 42/45 | 1 | $0.196 |
| Luna `medium` | + rules | 98% / 1.00 / 1.00 | 99% / 0.99 / 0.99 | 2.01s / 2.46s | 4.00s | 86% | 43/44, 43/45 | 0 | $0.206 |
| Haiku `low` | production | 98% / 0.95 / 0.97 | 85% / 0.89 / 1.00 | 1.36s / 1.51s | 2.27s | 100% | 39/44, 35/45 | 12 | $0.132 |
| Haiku `low` | + rules | 93% / 1.00 / 1.00 | 92% / 0.91 / 1.00 | 1.47s / 1.72s | 3.22s | 93% | 39/44, 37/45 | 8 | $0.137 |
| Haiku `medium` | production | 96% / 0.98 / 0.97 | 95% / 1.00 / 1.00 | 1.53s / 2.16s | 4.05s | 84% | 40/44, 42/45 | 3 | $0.151 |
| Haiku `medium` | + rules | 92% / 1.00 / 1.00 | 95% / 1.00 / 0.99 | 1.49s / 2.26s | 3.97s | 78% | 39/44, 41/45 | 5 | $0.154 |

"Queries fully right" counts queries where all 3 runs matched the expected filters and tags exactly. "Wrong on every run" counts queries (standard and hard together) missed on all 3 runs: consistent mistakes that a retry wouldn't fix.

## Trade-offs

**Robustness.**
- Luna with the rules is the most robust option. At either effort it has no query it gets wrong every time, and at `medium` it gets 86 of 89 queries right on every run. Its few misses are scattered one-off slips, on "special energy cards", "basic energy acceleration from the discard", "151 pokemon with free retreat", "stop my opponent from playing supporters", "put a pokemon from my deck onto the bench" and "cards like Rare Candy".
- Haiku `low` is the least robust. On the production prompt it has 12 queries it gets wrong on every run, 10 of them hard, and it drops to 85% filters and 0.89 tag precision on the hard set. Its errors are consistent, not noise:
  - it adds `damage-reduction` next to `damage-prevention`;
  - it tags Supporter lock as `item-lock`;
  - it invents `attack_cost ≤ 2` for "cheap attackers";
  - it reads "drag out a benched pokemon and hit it" as `snipe`;
  - it drops the set on "151 pokemon with free retreat".
- Haiku `medium` is much steadier (95% hard filters, tag precision 1.00) and is the closest Haiku gets to Luna, but it is no longer faster on hard queries (2.16s median, p95 4.05s).

**What the rules do.**
- **Luna:** small, consistent gains. Standard tag recall goes to 1.00 at both efforts, and the queries it gets wrong every time go from 1 to 0.
- **Haiku's tags:** fixed. Standard precision and recall are 1.00 at both efforts, "hit their bench for damage" gets both tags, and the stray `snipe` on the damage-counters query is gone. Haiku `low`'s hard-set precision improves only slightly (0.89 → 0.91).
- **Haiku's filters:** the category rule backfires. Haiku keeps adding `category: Pokemon` to "get pokemon back from the discard pile" and "put a pokemon from my deck onto the bench" on every run. It also starts adding `category: Energy` to energy-effect queries it got right before ("get energy out of my deck", "recover energy from my discard", "energy accel"). Standard filters fall from 98% to 93% at `low` and from 96% to 92% at `medium`. The rule seems to draw Haiku's attention to the field without teaching it when to leave the field empty.

**Latency.**
- Haiku `low` is the fastest everywhere (1.36s / 1.51s median, every hard call within 3s on the production prompt).
- Luna `low` is about 0.4–0.6s slower at the median, with p95 just under 3s on hard queries.
- Both `medium` configurations have hard-set p95s around 4s, at the edge of today's timeout.

**Cost.** Haiku is 20–25% cheaper per query than Luna at the same effort ($0.13–0.15 against $0.17–0.21 per 1,000 standard queries). At these prices the gap is about $4 per 100,000 parses, before the parse cache removes repeat queries.

## Issues found that affect every configuration

- **`energy_type` is a free-form string in the schema.** For "special energy cards", Luna returned `"Special Energy"` and `"special"` as well as `"Special"`, and Haiku sometimes left it out. Neither of the first two values matches a card. Making `energy_type` an enum (`"Basic"`, `"Special"`) in `parse_client.py` would remove this failure for every model; it's a schema change, so it bumps `PARSE_VERSION`.
- **"Under N HP".** The production prompt says "under 130 HP" means `hp.lte=130` (inclusive). Haiku follows the plain-English reading for "pokemon under 100 hp with free attacks" and returns `lte 99` on every run, at both efforts. It's scored as a miss because it contradicts the prompt, but it's arguably the prompt's convention that's surprising. Luna follows the prompt.
- **"put a pokemon from my deck onto the bench"** trips both models into `category: Pokemon`: Haiku on almost every run, Luna once or twice. It is the clearest category trap in the set.
- **"basic energy acceleration from the discard"** is the hardest query overall. Both models sometimes add `category: Energy`, `energy_type: Basic` or the `energy-recovery` tag. Attaching Energy from the discard is acceleration, but it also brings Energy back from the discard, so `energy-recovery` is defensible. The maintainer may want to accept it.

## Results: production prompt

Standard: 44 queries. Hard: 45 queries, scored separately.

| Configuration | Cases | Calls | Errors | Median | p95 | ≤2s | ≤3s | ≤4s | ≤6s | ≤8s | Reasoning tok | Completion tok | Cached | Filters exact | Tag P | Tag R | $ / 1k queries |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `gpt-5.6-luna / low` | standard | 132 | 0 | 1.73s | 2.35s | 80% | 99% | 100% | 100% | 100% | 3 | 107 | 100% | 98% | 1.00 | 0.97 | $0.169 |
| `gpt-5.6-luna / low` | hard | 135 | 0 | 2.12s | 2.99s | 41% | 96% | 99% | 100% | 100% | 30 | 144 | 100% | 97% | 0.97 | 1.00 | $0.214 |
| `gpt-5.6-luna / medium` | standard | 132 | 0 | 2.03s | 2.75s | 48% | 97% | 100% | 100% | 100% | 24 | 129 | 100% | 98% | 0.99 | 0.97 | $0.196 |
| `gpt-5.6-luna / medium` | hard | 135 | 0 | 2.47s | 3.73s | 13% | 79% | 97% | 100% | 100% | 59 | 173 | 100% | 98% | 1.00 | 0.99 | $0.249 |
| `claude-haiku-5-5 / low` | standard | 132 | 0 | 1.36s | 2.27s | 88% | 98% | 100% | 100% | 100% | 5 | 173 | 100% | 98% | 0.95 | 0.97 | $0.132 |
| `claude-haiku-5-5 / low` | hard | 135 | 0 | 1.51s | 2.27s | 88% | 100% | 100% | 100% | 100% | 6 | 190 | 100% | 85% | 0.89 | 1.00 | $0.141 |
| `claude-haiku-5-5 / medium` | standard | 132 | 0 | 1.53s | 3.23s | 77% | 94% | 98% | 100% | 100% | 44 | 211 | 100% | 96% | 0.98 | 0.97 | $0.151 |
| `claude-haiku-5-5 / medium` | hard | 135 | 0 | 2.16s | 4.05s | 44% | 84% | 95% | 100% | 100% | 152 | 332 | 100% | 95% | 1.00 | 1.00 | $0.213 |

Whole run (1072 calls including warm-ups, 0 failed): 3,466,456 input tokens (3,445,510 cached), 195,474 output tokens (43,430 of them reasoning), **$0.20**.

### `concept_rewritten` samples (run 1)

**energy accel**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low` | attach extra Energy beyond the one-per-turn manual attachment |
| `gpt-5.6-luna / medium` | attach extra Energy from your hand or deck beyond the one-per-turn attachment |
| `claude-haiku-5-5 / low` | attach extra Energy from your hand or deck beyond the one-per-turn attachment |
| `claude-haiku-5-5 / medium` | attach extra Energy from your hand or deck beyond the one-per-turn attachment |

**stall the opponent**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low` | waste the opponent's turn or stall the game without trading KOs, such as blocking attacks or forcing skips |
| `gpt-5.6-luna / medium` | waste the opponent's turn or stall the game without trading KOs |
| `claude-haiku-5-5 / low` | waste the opponent's turn or stall the game without trading knockouts, blocking attacks, forcing skips, or running the clock |
| `claude-haiku-5-5 / medium` | waste the opponent's turn or stall the game without trading knockouts, blocking attacks, forcing skips, or running the clock |

**put damage counters on their bench**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low` | Put damage counters directly on one or more of the opponent's Benched Pokémon, bypassing damage. |
| `gpt-5.6-luna / medium` | Put damage counters directly on one or more of the opponent's Benched Pokémon. |
| `claude-haiku-5-5 / low` | put damage counters on one or more of the opponent's Benched Pokémon without dealing damage to the Active Pokémon |
| `claude-haiku-5-5 / medium` | place damage counters on the opponent's Benched Pokémon without dealing damage |

**stadium that punishes ex**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low` | Apply a detrimental effect to Pokémon ex |
| `gpt-5.6-luna / medium` | has an effect that penalizes Pokémon ex |
| `claude-haiku-5-5 / low` | Stadium that deals extra damage or applies a penalty to the opponent's Pokémon ex when they are Active or on the Bench |
| `claude-haiku-5-5 / medium` | Stadium card whose effect penalizes or deals extra damage to Pokémon ex |

**punish them for attacking me**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low` | Deal damage back to the opponent's attacking Pokémon when your Pokémon is hit. |
| `gpt-5.6-luna / medium` | deal damage back to the opponent's attacking Pokémon when your Pokémon is hit |
| `claude-haiku-5-5 / low` | deal damage back to an attacking Pokémon when your Pokémon is hit by an attack |
| `claude-haiku-5-5 / medium` | when this Pokémon is damaged by an opponent's attack, deal damage back to the attacking Pokémon |

### Per-query disagreements

**get pokemon back from the discard pile** (expected `{}` · recovery)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{}` · recovery |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon"}` · recovery<br>`{}` · recovery |
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
| `gpt-5.6-luna / medium` | `{"category": "Trainer", "trainer_type": "Item"}` · search |
| `claude-haiku-5-5 / low` | `{"category": "Trainer", "trainer_type": "Item"}` · search |
| `claude-haiku-5-5 / medium` | `{"category": "Trainer", "trainer_type": "Item"}` · search |

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
| `claude-haiku-5-5 / low` | `{"category": "Trainer", "trainer_type": "Stadium"}` · counter-damage<br>`{"category": "Trainer", "trainer_type": "Stadium"}` · (no tags) |
| `claude-haiku-5-5 / medium` | `{"category": "Trainer", "trainer_type": "Stadium"}` · (no tags) |

**big hp basic** (expected `{"stage": "Basic"}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon", "stage": "Basic"}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon", "stage": "Basic"}` · (no tags) |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon", "stage": "Basic"}` · (no tags)<br>`{"stage": "Basic"}` · (no tags) |
| `claude-haiku-5-5 / medium` | `{"stage": "Basic"}` · (no tags) |

**pokemon with no retreat cost** (expected `{"category": "Pokemon", "retreat": {"lte": 0}}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}}` · (no tags)<br>`{"category": "Pokemon"}` · retreat-reduction |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}}` · (no tags) |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}}` · (no tags) |

**switch out even if they block retreating** (expected `{}` · switch)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{}` · switch |
| `gpt-5.6-luna / medium` | `{}` · switch |
| `claude-haiku-5-5 / low` | `{}` · movement-lock, switch<br>`{}` · switch |
| `claude-haiku-5-5 / medium` | `{}` · switch |

**special energy cards** (expected `{"category": "Energy", "energy_type": "Special"}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Energy", "energy_type": "Special Energy"}` · (no tags)<br>`{"category": "Energy", "energy_type": "Special"}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"category": "Energy", "energy_type": "Special"}` · (no tags)<br>`{"category": "Energy", "energy_type": "special"}` · (no tags) |
| `claude-haiku-5-5 / low` | `{"category": "Energy", "energy_type": "Special"}` · (no tags) |
| `claude-haiku-5-5 / medium` | `{"category": "Energy", "energy_type": "Special"}` · (no tags)<br>`{"category": "Energy"}` · (no tags) |

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
| `gpt-5.6-luna / medium` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}, "set_id": "sv03.5"}` · (no tags)<br>`{"category": "Pokemon", "retreat": {"lte": 0}, "set_id": "sv03.5"}` · (no tags) |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}}` · (no tags) |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}, "set_id": "sv03.5"}` · (no tags) |

**stage 2 with 300+ hp and a 1-energy attack** — hard (expected `{"stage": "Stage 2", "hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon", "hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}, "stage": "Stage 2"}` · (no tags)<br>`{"hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}, "stage": "Stage 2"}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}, "stage": "Stage 2"}` · (no tags) |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon", "hp": {"gte": 300}, "attack_cost": {"lte": 1}, "stage": "Stage 2"}` · (no tags) |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon", "hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}, "stage": "Stage 2"}` · (no tags)<br>`{"category": "Pokemon", "hp": {"gte": 300}, "attack_cost": {"lte": 1}, "stage": "Stage 2"}` · (no tags) |

**ace spec items that get cards back from the discard** — hard (expected `{"sub_category": ["ace-spec"], "trainer_type": "Item"}` · recovery)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Trainer", "sub_category": ["ace-spec"], "trainer_type": "Item"}` · recovery<br>`{"sub_category": ["ace-spec"], "trainer_type": "Item"}` · recovery |
| `gpt-5.6-luna / medium` | `{"category": "Trainer", "sub_category": ["ace-spec"], "trainer_type": "Item"}` · recovery |
| `claude-haiku-5-5 / low` | `{"category": "Trainer", "sub_category": ["ace-spec"], "trainer_type": "Item"}` · recovery |
| `claude-haiku-5-5 / medium` | `{"category": "Trainer", "sub_category": ["ace-spec"], "trainer_type": "Item"}` · recovery |

**turbo evolve my pokemon** — hard (expected `{}` · evolution-accel)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{}` · evolution-accel |
| `gpt-5.6-luna / medium` | `{}` · evolution-accel |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon"}` · evolution-accel |
| `claude-haiku-5-5 / medium` | `{}` · evolution-accel |

**colorless attackers that get stronger with more benched pokemon** — hard (expected `{"category": "Pokemon", "types": ["Colorless"]}` · damage-scaling)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon", "types": ["Colorless"]}` · damage-scaling |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon", "types": ["Colorless"]}` · damage-scaling |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon", "types": ["Colorless"]}` · damage-scaling |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon", "types": ["Colorless"]}` · damage-scaling<br>`{"types": ["Colorless"]}` · damage-scaling |

**fire or water ex that accelerate energy** — hard (expected `{"category": "Pokemon", "types": ["Fire", "Water"], "sub_category": ["ex"]}` · acceleration)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon", "sub_category": ["ex"], "types": ["Fire", "Water"]}` · acceleration |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon", "sub_category": ["ex"], "types": ["Fire", "Water"]}` · acceleration |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon", "sub_category": ["ex"], "types": ["Fire", "Water"]}` · acceleration |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon", "sub_category": ["ex"], "types": ["Fire", "Water"]}` · acceleration<br>`{"sub_category": ["ex"], "types": ["Fire", "Water"]}` · acceleration |

**stage 2 grass pokemon over 150 hp from Temporal Forces** — hard (expected `{"category": "Pokemon", "stage": "Stage 2", "types": ["Grass"], "hp": {"gte": 150}, "set_id": "sv05"}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon", "types": ["Grass"], "hp": {"gte": 151}, "stage": "Stage 2", "set_id": "sv05"}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon", "types": ["Grass"], "hp": {"gte": 150}, "stage": "Stage 2", "set_id": "sv05"}` · (no tags) |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon", "types": ["Grass"], "hp": {"gte": 150}, "stage": "Stage 2", "set_id": "sv05"}` · (no tags)<br>`{"category": "Pokemon", "types": ["Grass"], "hp": {"gte": 151}, "stage": "Stage 2", "set_id": "sv05"}` · (no tags) |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon", "types": ["Grass"], "hp": {"gte": 150}, "stage": "Stage 2", "set_id": "sv05"}` · (no tags)<br>`{"category": "Pokemon", "types": ["Grass"], "hp": {"gte": 151}, "stage": "Stage 2", "set_id": "sv05"}` · (no tags) |

**pokemon under 100 hp with free attacks** — hard (expected `{"category": "Pokemon", "hp": {"lte": 100}, "attack_cost": {"lte": 0}}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon", "hp": {"lte": 100}, "attack_cost": {"gte": 0, "lte": 0}}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon", "hp": {"lte": 100}, "attack_cost": {"gte": 0, "lte": 0}}` · (no tags)<br>`{"category": "Pokemon", "hp": {"lte": 100}, "attack_cost": {"lte": 0}}` · (no tags) |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon", "hp": {"lte": 100}, "attack_cost": {"gte": 0, "lte": 0}}` · (no tags) |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon", "hp": {"lte": 99}, "attack_cost": {"gte": 0, "lte": 0}}` · (no tags)<br>`{"category": "Pokemon", "hp": {"lte": 99}, "attack_cost": {"lte": 0}}` · (no tags) |

**items that are not ace spec** — hard (expected `{"trainer_type": "Item"}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Trainer", "trainer_type": "Item"}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"category": "Trainer", "trainer_type": "Item"}` · (no tags) |
| `claude-haiku-5-5 / low` | `{}` · (no tags) |
| `claude-haiku-5-5 / medium` | `{"category": "Trainer", "trainer_type": "Item"}` · (no tags)<br>`{"trainer_type": "Item"}` · (no tags) |

**ace spec that stops abilities** — hard (expected `{"sub_category": ["ace-spec"]}` · ability-lock)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"sub_category": ["ace-spec"]}` · ability-lock |
| `gpt-5.6-luna / medium` | `{"sub_category": ["ace-spec"]}` · ability-lock |
| `claude-haiku-5-5 / low` | `{"category": "Trainer", "sub_category": ["ace-spec"]}` · ability-lock |
| `claude-haiku-5-5 / medium` | `{"category": "Trainer", "sub_category": ["ace-spec"]}` · ability-lock<br>`{"sub_category": ["ace-spec"]}` · ability-lock |

**put a pokemon from my deck onto the bench** — hard (expected `{}` · search)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon"}` · search<br>`{}` · search |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon"}` · search<br>`{}` · search |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon"}` · search |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon"}` · search<br>`{}` · search |

**basic energy acceleration from the discard** — hard (expected `{}` · acceleration)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{}` · acceleration |
| `gpt-5.6-luna / medium` | `{}` · acceleration |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon", "energy_type": "Basic"}` · acceleration, energy-recovery<br>`{"category": "Pokemon"}` · acceleration, energy-recovery |
| `claude-haiku-5-5 / medium` | `{"category": "Energy"}` · acceleration<br>`{}` · acceleration |

**pokemon that block damage from basic pokemon** — hard (expected `{"category": "Pokemon"}` · damage-prevention)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon"}` · damage-prevention |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon"}` · damage-prevention |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon"}` · damage-prevention, damage-reduction |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon"}` · damage-prevention |

**pokemon that hit harder the more damage they have** — hard (expected `{"category": "Pokemon"}` · damage-scaling)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon"}` · damage-scaling<br>`{}` · damage-scaling |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon"}` · damage-scaling<br>`{}` · damage-scaling |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon"}` · damage-scaling |
| `claude-haiku-5-5 / medium` | `{"category": "Pokemon"}` · damage-scaling |

**cards like Rare Candy** — hard (expected `{}` · evolution-accel)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"trainer_type": "Item"}` · evolution-accel<br>`{}` · evolution-accel |
| `gpt-5.6-luna / medium` | `{}` · evolution-accel |
| `claude-haiku-5-5 / low` | `{}` · evolution-accel |
| `claude-haiku-5-5 / medium` | `{}` · evolution-accel |

**drag out a benched pokemon and hit it** — hard (expected `{}` · gust)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{}` · gust |
| `gpt-5.6-luna / medium` | `{}` · gust |
| `claude-haiku-5-5 / low` | `{"category": "Trainer", "trainer_type": "Item"}` · gust, snipe<br>`{"category": "Trainer"}` · gust, snipe<br>`{}` · gust, snipe |
| `claude-haiku-5-5 / medium` | `{}` · gust |

**reduce the retreat cost of my whole bench** — hard (expected `{}` · retreat-reduction)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{}` · retreat-reduction |
| `gpt-5.6-luna / medium` | `{}` · retreat-reduction<br>`{}` · (no tags) |
| `claude-haiku-5-5 / low` | `{}` · retreat-reduction |
| `claude-haiku-5-5 / medium` | `{}` · retreat-reduction |

**stop my opponent from playing supporters** — hard (expected `{}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{}` · item-lock<br>`{}` · stall<br>`{}` · (no tags) |
| `gpt-5.6-luna / medium` | `{}` · (no tags) |
| `claude-haiku-5-5 / low` | `{}` · item-lock |
| `claude-haiku-5-5 / medium` | `{}` · (no tags) |

**cheap attackers with big damage** — hard (expected `{}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low` | `{"category": "Pokemon"}` · (no tags)<br>`{}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon"}` · (no tags)<br>`{}` · (no tags) |
| `claude-haiku-5-5 / low` | `{"category": "Pokemon", "attack_cost": {"lte": 2}}` · damage-scaling<br>`{"category": "Pokemon", "attack_cost": {"lte": 2}}` · (no tags) |
| `claude-haiku-5-5 / medium` | `{}` · (no tags) |


## Results: with the candidate rules

Standard: 44 queries. Hard: 45 queries, scored separately.

| Configuration | Cases | Calls | Errors | Median | p95 | ≤2s | ≤3s | ≤4s | ≤6s | ≤8s | Reasoning tok | Completion tok | Cached | Filters exact | Tag P | Tag R | $ / 1k queries |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `gpt-5.6-luna / low + rules` | standard | 132 | 0 | 1.73s | 2.32s | 80% | 99% | 100% | 100% | 100% | 5 | 108 | 100% | 99% | 1.00 | 1.00 | $0.176 |
| `gpt-5.6-luna / low + rules` | hard | 135 | 0 | 2.00s | 2.96s | 50% | 96% | 99% | 100% | 100% | 28 | 141 | 100% | 97% | 0.97 | 1.00 | $0.215 |
| `gpt-5.6-luna / medium + rules` | standard | 132 | 0 | 2.01s | 3.18s | 49% | 95% | 99% | 100% | 100% | 27 | 133 | 100% | 98% | 1.00 | 1.00 | $0.206 |
| `gpt-5.6-luna / medium + rules` | hard | 135 | 0 | 2.46s | 4.00s | 13% | 86% | 95% | 99% | 99% | 58 | 173 | 100% | 99% | 0.99 | 0.99 | $0.254 |
| `claude-haiku-5-5 / low + rules` | standard | 132 | 0 | 1.47s | 2.26s | 92% | 99% | 100% | 100% | 100% | 6 | 174 | 100% | 93% | 1.00 | 1.00 | $0.137 |
| `claude-haiku-5-5 / low + rules` | hard | 135 | 0 | 1.72s | 3.22s | 81% | 93% | 99% | 100% | 100% | 33 | 218 | 100% | 92% | 0.91 | 1.00 | $0.159 |
| `claude-haiku-5-5 / medium + rules` | standard | 132 | 0 | 1.49s | 2.79s | 82% | 97% | 99% | 100% | 100% | 41 | 208 | 100% | 92% | 1.00 | 1.00 | $0.154 |
| `claude-haiku-5-5 / medium + rules` | hard | 135 | 0 | 2.26s | 3.97s | 41% | 78% | 96% | 100% | 100% | 168 | 349 | 100% | 95% | 1.00 | 0.99 | $0.225 |

Whole run (1072 calls including warm-ups, 0 failed): 3,812,712 input tokens (3,786,012 cached), 201,633 output tokens (49,053 of them reasoning), **$0.21**.

### `concept_rewritten` samples (run 1)

**energy accel**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low + rules` | attach extra Energy from your hand or deck beyond the one-per-turn attachment |
| `gpt-5.6-luna / medium + rules` | attach extra Energy from your hand or deck beyond the one-per-turn attachment |
| `claude-haiku-5-5 / low + rules` | attach extra Energy from your hand or deck beyond the one-per-turn attachment |
| `claude-haiku-5-5 / medium + rules` | attach extra Energy from your hand or deck beyond the one-per-turn attachment |

**stall the opponent**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low + rules` | waste the opponent's turn or stall the game without trading KOs |
| `gpt-5.6-luna / medium + rules` | waste the opponent's turn or delay the game without trading KOs |
| `claude-haiku-5-5 / low + rules` | waste the opponent's turn or stall the game without trading knockouts, blocking attacks, forcing skips, or running the clock |
| `claude-haiku-5-5 / medium + rules` | waste the opponent's turn or stall the game without trading knockouts, blocking attacks, forcing skips, or running the clock |

**put damage counters on their bench**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low + rules` | Place damage counters directly on one or more of the opponent's Benched Pokémon |
| `gpt-5.6-luna / medium + rules` | Put damage counters directly on the opponent's Benched Pokémon. |
| `claude-haiku-5-5 / low + rules` | place damage counters on one or more of the opponent's Benched Pokemon |
| `claude-haiku-5-5 / medium + rules` | place damage counters directly on the opponent's Benched Pokémon, not dealing damage |

**stadium that punishes ex**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low + rules` | penalizes Pokémon ex |
| `gpt-5.6-luna / medium + rules` | punishes Pokémon ex |
| `claude-haiku-5-5 / low + rules` | Stadium card whose effect deals extra damage or otherwise penalizes the opponent's Pokémon ex when in play |
| `claude-haiku-5-5 / medium + rules` | Stadium card that deals extra damage or imposes a penalty on the opponent's Pokémon ex |

**punish them for attacking me**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5.6-luna / low + rules` | deal damage back to the opponent's attacking Pokémon when it attacks me |
| `gpt-5.6-luna / medium + rules` | deal damage back to the opponent's attacking Pokémon when it attacks |
| `claude-haiku-5-5 / low + rules` | when this Pokemon is damaged by an opponent's attack, deal damage back to the attacking Pokemon |
| `claude-haiku-5-5 / medium + rules` | deal damage back to the attacking Pokémon when this Pokémon is hit by an opponent's attack |

### Per-query disagreements

**energy accel** (expected `{}` · acceleration)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{}` · acceleration |
| `gpt-5.6-luna / medium + rules` | `{}` · acceleration |
| `claude-haiku-5-5 / low + rules` | `{"category": "Pokemon"}` · acceleration<br>`{}` · acceleration |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Energy"}` · acceleration<br>`{}` · acceleration |

**get pokemon back from the discard pile** (expected `{}` · recovery)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{}` · recovery |
| `gpt-5.6-luna / medium + rules` | `{}` · recovery |
| `claude-haiku-5-5 / low + rules` | `{"category": "Pokemon"}` · recovery |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Pokemon"}` · recovery |

**attacker that does more damage for each energy attached** (expected `{}` · damage-scaling)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{"category": "Pokemon"}` · damage-scaling |
| `gpt-5.6-luna / medium + rules` | `{"category": "Pokemon"}` · damage-scaling<br>`{}` · damage-scaling |
| `claude-haiku-5-5 / low + rules` | `{"category": "Pokemon"}` · damage-scaling |
| `claude-haiku-5-5 / medium + rules` | `{}` · damage-scaling |

**get energy out of my deck** (expected `{}` · energy-search)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{}` · energy-search |
| `gpt-5.6-luna / medium + rules` | `{}` · energy-search |
| `claude-haiku-5-5 / low + rules` | `{"category": "Energy"}` · energy-search |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Energy"}` · energy-search |

**big hp basic** (expected `{"stage": "Basic"}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{"category": "Pokemon", "stage": "Basic"}` · (no tags) |
| `gpt-5.6-luna / medium + rules` | `{"category": "Pokemon", "stage": "Basic"}` · (no tags)<br>`{"stage": "Basic"}` · (no tags) |
| `claude-haiku-5-5 / low + rules` | `{"category": "Pokemon", "hp": {"gte": 200}, "stage": "Basic"}` · (no tags)<br>`{"category": "Pokemon", "stage": "Basic"}` · (no tags) |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Pokemon", "stage": "Basic"}` · (no tags)<br>`{"stage": "Basic"}` · (no tags) |

**pokemon with no retreat cost** (expected `{"category": "Pokemon", "retreat": {"lte": 0}}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}}` · (no tags)<br>`{"category": "Pokemon", "retreat": {"lte": 0}}` · (no tags) |
| `gpt-5.6-luna / medium + rules` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}}` · (no tags)<br>`{"category": "Pokemon", "retreat": {"lte": 0}}` · (no tags) |
| `claude-haiku-5-5 / low + rules` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}}` · (no tags) |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}}` · (no tags) |

**special energy cards** (expected `{"category": "Energy", "energy_type": "Special"}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{"category": "Energy", "energy_type": "Special"}` · (no tags)<br>`{"category": "Energy"}` · (no tags) |
| `gpt-5.6-luna / medium + rules` | `{"category": "Energy", "energy_type": "Special"}` · (no tags)<br>`{"category": "Energy"}` · (no tags) |
| `claude-haiku-5-5 / low + rules` | `{"category": "Energy", "energy_type": "Special"}` · (no tags) |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Energy", "energy_type": "Special"}` · (no tags)<br>`{"category": "Energy"}` · (no tags) |

**recover energy from my discard** (expected `{}` · energy-recovery)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{}` · energy-recovery |
| `gpt-5.6-luna / medium + rules` | `{}` · energy-recovery |
| `claude-haiku-5-5 / low + rules` | `{"category": "Energy"}` · energy-recovery<br>`{}` · energy-recovery |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Energy"}` · energy-recovery |

**151 pokemon with free retreat** — hard (expected `{"category": "Pokemon", "set_id": "sv03.5", "retreat": {"lte": 0}}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{"category": "Pokemon", "retreat": {"lte": 0}, "set_id": "sv03.5"}` · (no tags)<br>`{"category": "Pokemon", "set_id": "sv03.5"}` · retreat-reduction |
| `gpt-5.6-luna / medium + rules` | `{"category": "Pokemon", "retreat": {"lte": 0}, "set_id": "sv03.5"}` · (no tags)<br>`{"category": "Pokemon", "set_id": "sv03.5"}` · retreat-reduction |
| `claude-haiku-5-5 / low + rules` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}, "set_id": "sv03.5"}` · retreat-reduction<br>`{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}, "set_id": "sv03.5"}` · (no tags) |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}, "set_id": "sv03.5"}` · (no tags) |

**stage 2 with 300+ hp and a 1-energy attack** — hard (expected `{"stage": "Stage 2", "hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{"category": "Pokemon", "hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}, "stage": "Stage 2"}` · (no tags)<br>`{"hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}, "stage": "Stage 2"}` · (no tags) |
| `gpt-5.6-luna / medium + rules` | `{"hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}, "stage": "Stage 2"}` · (no tags) |
| `claude-haiku-5-5 / low + rules` | `{"category": "Pokemon", "hp": {"gte": 300}, "attack_cost": {"lte": 1}, "stage": "Stage 2"}` · (no tags) |
| `claude-haiku-5-5 / medium + rules` | `{"hp": {"gte": 300}, "attack_cost": {"gte": 1, "lte": 1}, "stage": "Stage 2"}` · (no tags)<br>`{"category": "Pokemon", "hp": {"gte": 300}, "attack_cost": {"lte": 1}, "stage": "Stage 2"}` · (no tags) |

**attack that discards their energy and the top card of their deck** — hard (expected `{}` · energy-removal, mill)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{}` · energy-removal, mill |
| `gpt-5.6-luna / medium + rules` | `{"category": "Pokemon"}` · energy-removal, mill<br>`{}` · energy-removal, mill |
| `claude-haiku-5-5 / low + rules` | `{}` · energy-removal, mill |
| `claude-haiku-5-5 / medium + rules` | `{}` · energy-removal, mill |

**colorless attackers that get stronger with more benched pokemon** — hard (expected `{"category": "Pokemon", "types": ["Colorless"]}` · damage-scaling)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{"category": "Pokemon", "types": ["Colorless"]}` · damage-scaling |
| `gpt-5.6-luna / medium + rules` | `{"category": "Pokemon", "types": ["Colorless"]}` · damage-scaling |
| `claude-haiku-5-5 / low + rules` | `{"types": ["Colorless"]}` · damage-scaling |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Pokemon", "types": ["Colorless"]}` · damage-scaling |

**stage 2 grass pokemon over 150 hp from Temporal Forces** — hard (expected `{"category": "Pokemon", "stage": "Stage 2", "types": ["Grass"], "hp": {"gte": 150}, "set_id": "sv05"}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{"category": "Pokemon", "types": ["Grass"], "hp": {"gte": 151}, "stage": "Stage 2", "set_id": "sv05"}` · (no tags) |
| `gpt-5.6-luna / medium + rules` | `{"category": "Pokemon", "types": ["Grass"], "hp": {"gte": 150}, "stage": "Stage 2", "set_id": "sv05"}` · (no tags)<br>`{"category": "Pokemon", "types": ["Grass"], "hp": {"gte": 151}, "stage": "Stage 2", "set_id": "sv05"}` · (no tags) |
| `claude-haiku-5-5 / low + rules` | `{"category": "Pokemon", "types": ["Grass"], "hp": {"gte": 151}, "stage": "Stage 2", "set_id": "sv05"}` · (no tags) |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Pokemon", "types": ["Grass"], "hp": {"gte": 151}, "stage": "Stage 2", "set_id": "sv05"}` · (no tags) |

**pokemon under 100 hp with free attacks** — hard (expected `{"category": "Pokemon", "hp": {"lte": 100}, "attack_cost": {"lte": 0}}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{"category": "Pokemon", "hp": {"lte": 100}, "attack_cost": {"lte": 0}}` · (no tags) |
| `gpt-5.6-luna / medium + rules` | `{"category": "Pokemon", "hp": {"lte": 100}, "attack_cost": {"gte": 0, "lte": 0}}` · (no tags) |
| `claude-haiku-5-5 / low + rules` | `{"category": "Pokemon", "hp": {"lte": 99}, "attack_cost": {"gte": 0, "lte": 0}}` · (no tags) |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Pokemon", "hp": {"lte": 99}, "attack_cost": {"gte": 0, "lte": 0}}` · (no tags) |

**ace spec that stops abilities** — hard (expected `{"sub_category": ["ace-spec"]}` · ability-lock)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{"sub_category": ["ace-spec"]}` · ability-lock |
| `gpt-5.6-luna / medium + rules` | `{"sub_category": ["ace-spec"]}` · ability-lock |
| `claude-haiku-5-5 / low + rules` | `{"category": "Trainer", "sub_category": ["ace-spec"]}` · ability-lock |
| `claude-haiku-5-5 / medium + rules` | `{"sub_category": ["ace-spec"]}` · ability-lock |

**put a pokemon from my deck onto the bench** — hard (expected `{}` · search)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{"category": "Pokemon"}` · search<br>`{}` · search |
| `gpt-5.6-luna / medium + rules` | `{}` · search |
| `claude-haiku-5-5 / low + rules` | `{"category": "Pokemon"}` · search |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Pokemon"}` · search |

**basic energy acceleration from the discard** — hard (expected `{}` · acceleration)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{"category": "Energy", "energy_type": "Basic"}` · acceleration<br>`{"category": "Energy"}` · acceleration, energy-recovery<br>`{}` · acceleration |
| `gpt-5.6-luna / medium + rules` | `{}` · acceleration |
| `claude-haiku-5-5 / low + rules` | `{"category": "Energy"}` · acceleration, energy-recovery<br>`{"category": "Energy"}` · acceleration<br>`{}` · acceleration, energy-recovery |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Energy"}` · acceleration<br>`{}` · acceleration |

**pokemon that block damage from basic pokemon** — hard (expected `{"category": "Pokemon"}` · damage-prevention)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{"category": "Pokemon"}` · damage-prevention |
| `gpt-5.6-luna / medium + rules` | `{"category": "Pokemon"}` · damage-prevention |
| `claude-haiku-5-5 / low + rules` | `{"category": "Pokemon"}` · damage-prevention, damage-reduction |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Pokemon"}` · damage-prevention |

**bench barrier** — hard (expected `{}` · damage-prevention)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{}` · damage-prevention |
| `gpt-5.6-luna / medium + rules` | `{}` · damage-prevention |
| `claude-haiku-5-5 / low + rules` | `{}` · damage-prevention |
| `claude-haiku-5-5 / medium + rules` | `{}` · damage-prevention<br>`{}` · (no tags) |

**cards like Rare Candy** — hard (expected `{}` · evolution-accel)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{}` · evolution-accel |
| `gpt-5.6-luna / medium + rules` | `{}` · evolution-accel<br>`{}` · (no tags) |
| `claude-haiku-5-5 / low + rules` | `{}` · evolution-accel |
| `claude-haiku-5-5 / medium + rules` | `{}` · evolution-accel |

**drag out a benched pokemon and hit it** — hard (expected `{}` · gust)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{}` · gust |
| `gpt-5.6-luna / medium + rules` | `{}` · gust |
| `claude-haiku-5-5 / low + rules` | `{}` · gust, snipe<br>`{}` · gust |
| `claude-haiku-5-5 / medium + rules` | `{}` · gust |

**stop my opponent from playing supporters** — hard (expected `{}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{}` · item-lock<br>`{}` · (no tags) |
| `gpt-5.6-luna / medium + rules` | `{}` · (no tags) |
| `claude-haiku-5-5 / low + rules` | `{}` · hand-disruption<br>`{}` · item-lock |
| `claude-haiku-5-5 / medium + rules` | `{}` · (no tags) |

**cheap attackers with big damage** — hard (expected `{}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5.6-luna / low + rules` | `{"category": "Pokemon"}` · (no tags)<br>`{}` · (no tags) |
| `gpt-5.6-luna / medium + rules` | `{"category": "Pokemon"}` · (no tags)<br>`{}` · (no tags) |
| `claude-haiku-5-5 / low + rules` | `{"attack_cost": {"lte": 1}}` · (no tags)<br>`{"category": "Pokemon", "attack_cost": {"lte": 2}}` · (no tags) |
| `claude-haiku-5-5 / medium + rules` | `{"category": "Pokemon"}` · (no tags)<br>`{}` · (no tags) |

