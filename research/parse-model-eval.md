# Parse model eval: gpt-5-mini vs GPT-5.6 Luna, by reasoning effort

**Ticket:** [#85: Compare parse models and reasoning efforts](https://github.com/Di-or/ultraball/issues/85)
**Date:** 2026-10-06, measured against `main` at `b127a00` (`PARSE_VERSION` v4, 28-tag v2 taxonomy)
**Rerun:** `uv run python -m scripts.parse_model_eval` (needs `OPENAI_API_KEY`). `--report` re-renders the tables below from `parse-model-eval-raw.json` without calling the API.

This file holds measurements only. It does not choose the parse model or change the 4s timeout; both are left to a follow-up ticket.

## Method

- **Request:** the production parse request. System prompt and strict JSON schema are imported from `app/clients/parse_client.py`, plus an explicit `reasoning_effort`. Input measured 1,429–1,437 tokens per call. That is below the ~1,670 estimated in #85; the gap is most likely the estimate's count for the schema.
- **Queries:** the 25 queries in `scripts/parse_eval_queries.json`, each with an expected `filters` object and expected tags. Some queries also list alternative accepted `filters`. For example, "supporters" may or may not also set `category: Trainer`; both search the same cards.
- **Runs:** 6 configurations × 25 queries × 3 runs = 450 measured calls, plus one warm-up call per configuration so that the measured calls hit a cached prompt prefix. The timeout is 60s, so slow configurations still finish and get measured.
- **Latency:** wall-clock time around the HTTP call, using a fresh `httpx.AsyncClient` per call as `HostedParseClient` does, so connection setup is included. The configurations ran side by side, while calls within one configuration ran one after another. All calls came from one Windows machine on a home connection, in one session.
- **Scoring:**
  - **Filters exact:** strict-mode nulls and empty ranges are dropped, then the result is compared with the expected filters or an accepted alternative.
  - **Tag P / R:** micro-averaged over all calls; queries that expect no tags count any predicted tag against precision.
  - **Quality metrics** are computed over calls that answered. No call failed, so this made no difference here.
- **Cost:** from each call's measured `usage`, at $0.25 / $0.025 / $2.00 (gpt-5-mini) and $0.20 / $0.02 / $1.20 (Luna) per 1M uncached input / cached input / output tokens. Reasoning tokens bill as output. Luna's `usage` also reports `cache_write_tokens`, billed at 1.25× the uncached input rate ([model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna)). gpt-5-mini reports no cache writes.

## Results

| Configuration | Calls | Errors | Median | p95 | ≤2s | ≤3s | ≤4s | ≤6s | ≤8s | Reasoning tok | Completion tok | Cached | Filters exact | Tag P | Tag R | $ / 1k queries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `gpt-5-mini / minimal` | 75 | 0 | 1.83s | 2.96s | 64% | 96% | 97% | 100% | 100% | 0 | 164 | 88% | 73% | 0.79 | 1.00 | $0.402 |
| `gpt-5-mini / low` | 75 | 0 | 2.55s | 3.71s | 11% | 72% | 97% | 100% | 100% | 96 | 274 | 87% | 95% | 1.00 | 1.00 | $0.625 |
| `gpt-5-mini / medium` | 75 | 0 | 4.92s | 7.60s | 0% | 0% | 23% | 72% | 99% | 496 | 672 | 87% | 93% | 1.00 | 1.00 | $1.422 |
| `gpt-5.6-luna / none` | 75 | 0 | 1.97s | 2.34s | 57% | 100% | 100% | 100% | 100% | 0 | 106 | 100% | 93% | 1.00 | 0.95 | $0.157 |
| `gpt-5.6-luna / low` | 75 | 0 | 1.92s | 2.54s | 72% | 100% | 100% | 100% | 100% | 2 | 108 | 100% | 93% | 1.00 | 0.97 | $0.160 |
| `gpt-5.6-luna / medium` | 75 | 0 | 2.17s | 3.42s | 36% | 91% | 99% | 100% | 100% | 22 | 131 | 100% | 93% | 1.00 | 0.97 | $0.187 |


`≤Ns` is the share of calls that finished within N seconds. `Reasoning tok` and `Completion tok` are means per call. `Cached` is the share of input tokens served from cache.

### For reference: #80's gpt-5-mini numbers (old prompt, before #84)

3 queries per effort, through the 4s-timeout client:

| `reasoning_effort` | Latency | Reasoning tokens | Notes |
| --- | --- | --- | --- |
| default (unset) | 6.6s, 8.9s, 6.7s | 832 to 1216 | always over the 4s timeout |
| `low` | 4.8s, 4.1s, 2.4s | 128 to 384 | borderline |
| `minimal` | 2.4s, 2.3s, 1.4s | 0 | fits; tags noisier (4 tags for "stadium that punishes ex" against 0 to 1 at higher effort) |

With the longer glossary prompt from #84 and #83, gpt-5-mini uses fewer reasoning tokens than in #80: 496 mean at `medium`, against 832 to 1216 then. It is also faster at each effort. #80 measured only 3 queries per effort, so the two sets of numbers are only roughly comparable.

## Trade-offs

**Latency.**
- Every Luna effort and gpt-5-mini/`minimal` have medians under 2.2s.
- Under today's 4s timeout, all of those except gpt-5-mini/`minimal` complete at least 99% of calls; gpt-5-mini/`minimal` completes 97%.
- Luna/`none` and Luna/`low` have the tightest tails, with p95 of 2.34s and 2.54s.
- gpt-5-mini/`low` would fit the 4s timeout (97%) but not a 3s one (72%).
- gpt-5-mini/`medium`, which is what production sends today because it sets no effort, finishes only 23% of calls within 4s. That matches #80's finding that the parse almost always degrades to keyword-only.
- Luna barely reasons at `none` and `low` (0 to 2 reasoning tokens on average), and only lightly at `medium` (22).

**Tag quality.**
- gpt-5-mini/`minimal` is the only noisy configuration, with precision 0.79. It again over-tagged #80's query "stadium that punishes ex" with 1 to 3 wrong tags on every run, and sometimes listed six control tags for "stall the opponent".
- The glossary from #84 did not fix `minimal`'s noise. Every other configuration has tag precision 1.00.
- Luna's tag recall (0.95 to 0.97) is slightly below gpt-5-mini/`low` and `medium` (1.00). All of Luna's tag misses are on "retreat for free": in some runs Luna read it as a `retreat` = 0 filter with no tag, instead of the `switch` effect. That query is ambiguous (see below).

**Filters.**
- gpt-5-mini/`minimal` invents filters the query didn't state, e.g. `hp.gte` 150 or 200 for "big hp basic", and a 0-retreat filter for "retreat for free". Its exact-match rate is 73%.
- The others score 93% to 95%. Their misses are the `set_id` problem below (3 calls each), "retreat for free", and a stray `category: Pokemon` on one run each: "attacker that does more damage for each energy attached" (gpt-5-mini `low` and `medium`) and "get pokemon back from the discard pile" (Luna/`medium`).

**Rewrites.**
- Luna's `concept_rewritten` is short and close to the tag definitions.
- gpt-5-mini's rewrites are longer, and at `minimal` they sometimes list effects the query didn't ask for. In the "stall the opponent" sample it adds item lock.
- Luna/`none` sometimes drops the filter part of the concept. For "big hp basic" it gave "High maximum HP", which is arguably correct, since `Basic` went to `filters`.

**Cost per 1,000 queries.**
- Luna: $0.16 to $0.19 at every effort.
- gpt-5-mini: $0.40 (`minimal`), $0.63 (`low`), $1.42 (`medium`).
- Luna has the lower token prices and also writes shorter outputs.
- Luna cached nearly the whole prompt (1,420 to 1,431 tokens) on every measured call. gpt-5-mini cached it in 128-token blocks, 1,280 tokens on 220 of its 225 calls, which explains its 87% to 88% cached share.
- Luna's cache writes came to only 684 tokens across the run (651 on measured calls). Their cost is negligible.

## Findings outside the model choice

- **`set_id` can't come from the parser as it stands.** No configuration returned the TCGdex id `sv06` for "supporters from Twilight Masquerade". They returned the set name, `TWM`, or `sv6`, because the prompt doesn't list the sets or their ids. So a set named in a query would never match through `filters.set_id`. This costs every configuration 4 points of filter match.
- **Expected outputs to review** (the maintainer should review all of `parse_eval_queries.json`, as with the #81 examples):
  - "retreat for free" expects the `switch` tag and no filter. Reading it as "Pokémon with no retreat cost" (`retreat` = 0) is also defensible, and that reading is what moves Luna's recall.
  - "get energy out of my deck" expects `energy-search`. No configuration disagreed.
  - "hit their bench for damage" expects `snipe` only. gpt-5-mini/`minimal` sometimes added `spread`.

## Caveats

- One session from one network, on one day. Absolute latencies depend on the region and on OpenAI's load. The relative order is the stronger result.
- 75 calls per configuration, so p95 rests on the 4th-slowest call.
- Six configurations ran at the same time, so up to six requests were in flight together. The three Luna configurations share a prefix cache, so even their warm-ups were already cached; this has no effect on the measured calls, which all came after the warm-ups.
- `gpt-5.6-luna` is an alias with no dated snapshot, so these results may not hold if OpenAI updates the model behind it.

## Run details

Whole run (456 calls including warm-ups, 0 failed): 653,166 input tokens (606,815 cached), 110,322 output tokens (46,831 of them reasoning), **$0.22**.

### `concept_rewritten` samples (run 1)

**energy accel**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5-mini / minimal` | Attach extra Energy from your hand or other sources beyond the one normal manual attachment per turn (attach more than one Energy to your Pokémon in a single turn). |
| `gpt-5-mini / low` | Provide effects that let you attach extra Energy cards to your Pokémon beyond the one manual attachment per turn (examples: attach additional Energy from your hand or fetch+attach from deck). |
| `gpt-5-mini / medium` | Allow attaching extra Energy from hand, deck, discard pile, or card effects in addition to the one Energy you may normally manually attach each turn. |
| `gpt-5.6-luna / none` | attach extra Energy beyond the one-per-turn manual attachment |
| `gpt-5.6-luna / low` | Attach extra Energy from your hand or deck beyond the one-per-turn attachment. |
| `gpt-5.6-luna / medium` | attach extra Energy beyond the one normal manual attachment per turn |

**stall the opponent**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5-mini / minimal` | Cards that stall the opponent by preventing or skipping their attacks/effects, blocking their actions, or otherwise wasting turns (e.g., cards that stop attacks, force skips, lock Items, or impede play) without primarily relying on KO trades. |
| `gpt-5-mini / low` | cards that waste the opponent's turns or slow game progress without trading KOs — e.g. effects that prevent or block attacks, force the opponent to skip their attack, stop them from taking meaningful actions, or otherwise prolong the game state. |
| `gpt-5-mini / medium` | Prevent or delay the opponent from making meaningful progress—effects that block or negate attacks, force skipped turns or actions, prevent switching/retreating, or otherwise run down the clock without trading KOs. |
| `gpt-5.6-luna / none` | Waste the opponent’s turn or stall the game without trading KOs, such as by blocking attacks, preventing actions, or forcing skips. |
| `gpt-5.6-luna / low` | Waste the opponent's turn or stall the game without trading KOs, such as by blocking attacks, forcing skips, or otherwise preventing meaningful progress |
| `gpt-5.6-luna / medium` | Waste the opponent's turn or stall the game without trading KOs, such as by blocking attacks, forcing skips, or otherwise delaying the opponent. |

**put damage counters on their bench**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5-mini / minimal` | An effect that places damage counters directly on one or more of the opponent's Benched Pokémon (counter-placement targeted at Benched Pokémon). |
| `gpt-5-mini / low` | An effect that places damage counters directly onto one or more of the opponent's Benched Pokémon (i.e., put damage counters on opponent Benched Pokémon, bypassing regular damage mechanics). |
| `gpt-5-mini / medium` | Place damage counters directly onto one or more of the opponent's Benched Pokémon (damage as counters placed on Bench Pokémon rather than dealt as attack damage). |
| `gpt-5.6-luna / none` | Put damage counters directly on one or more of the opponent's Benched Pokémon. |
| `gpt-5.6-luna / low` | Place damage counters directly on one or more of the opponent's Benched Pokémon, bypassing damage calculation. |
| `gpt-5.6-luna / medium` | Place damage counters directly on one or more of the opponent's Benched Pokémon, bypassing damage. |

**stadium that punishes ex**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5-mini / minimal` | A Stadium Trainer card that applies a drawback or extra penalty specifically to Pokémon-ex (such as dealing extra damage to them, increasing their retreat cost, shutting off their Abilities, or changing Prize rules when they're Knocked Out). |
| `gpt-5-mini / low` | A Stadium card whose text applies a negative effect specifically to Pokémon-ex (cards with 'ex' in their name/type), e.g. increasing damage they take, preventing their attacks, discarding their Energy, or otherwise imposing penalties targeted at Pokémon-ex. |
| `gpt-5-mini / medium` | A Stadium card that applies a detrimental effect specifically to Pokémon-ex while they are in play (i.e., a persistent effect that targets cards with the 'Pokémon-ex' designation). |
| `gpt-5.6-luna / none` | Punishes Pokémon ex through a Stadium effect |
| `gpt-5.6-luna / low` | A Stadium card whose effect penalizes Pokémon ex |
| `gpt-5.6-luna / medium` | Stadium effect that penalizes Pokémon ex |

**big hp basic**

| Configuration | `concept_rewritten` |
| --- | --- |
| `gpt-5-mini / minimal` | Basic Pokémon card with very high HP (at least 200 HP) |
| `gpt-5-mini / low` | Find Basic Pokémon cards whose HP value is notably high compared to typical Basics (filter by a high HP threshold, e.g. HP >= X). |
| `gpt-5-mini / medium` | Basic Pokémon that have significantly higher-than-normal HP for a Basic (i.e., unusually large HP totals) |
| `gpt-5.6-luna / none` | High maximum HP |
| `gpt-5.6-luna / low` | High maximum HP |
| `gpt-5.6-luna / medium` | A Basic Pokémon with a high HP value |

### Per-query disagreements

**supporters from Twilight Masquerade** (expected `{"trainer_type": "Supporter", "set_id": "sv06"}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{"category": "Trainer", "trainer_type": "Supporter", "set_id": "Twilight Masquerade"}` · (no tags) |
| `gpt-5-mini / low` | `{"category": "Trainer", "trainer_type": "Supporter", "set_id": "Twilight Masquerade"}` · (no tags) |
| `gpt-5-mini / medium` | `{"category": "Trainer", "trainer_type": "Supporter", "set_id": "Twilight Masquerade"}` · (no tags) |
| `gpt-5.6-luna / none` | `{"category": "Trainer", "trainer_type": "Supporter", "set_id": "TWM"}` · (no tags)<br>`{"category": "Trainer", "trainer_type": "Supporter", "set_id": "twilight masquerade"}` · (no tags) |
| `gpt-5.6-luna / low` | `{"category": "Trainer", "trainer_type": "Supporter", "set_id": "TWM"}` · (no tags)<br>`{"category": "Trainer", "trainer_type": "Supporter", "set_id": "sv6"}` · (no tags)<br>`{"category": "Trainer", "trainer_type": "Supporter", "set_id": "twilight masquerade"}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"category": "Trainer", "trainer_type": "Supporter", "set_id": "TWM"}` · (no tags) |

**pokemon under 130 HP with 1 retreat** (expected `{"category": "Pokemon", "hp": {"lte": 130}, "retreat": {"gte": 1, "lte": 1}}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{"category": "Pokemon", "hp": {"lte": 130}, "retreat": {"gte": 1, "lte": 1}}` · (no tags)<br>`{"hp": {"lte": 130}, "retreat": {"gte": 1, "lte": 1}}` · (no tags) |
| `gpt-5-mini / low` | `{"category": "Pokemon", "hp": {"lte": 130}, "retreat": {"gte": 1, "lte": 1}}` · (no tags) |
| `gpt-5-mini / medium` | `{"category": "Pokemon", "hp": {"lte": 130}, "retreat": {"gte": 1, "lte": 1}}` · (no tags) |
| `gpt-5.6-luna / none` | `{"category": "Pokemon", "hp": {"lte": 130}, "retreat": {"gte": 1, "lte": 1}}` · (no tags) |
| `gpt-5.6-luna / low` | `{"category": "Pokemon", "hp": {"lte": 130}, "retreat": {"gte": 1, "lte": 1}}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon", "hp": {"lte": 130}, "retreat": {"gte": 1, "lte": 1}}` · (no tags) |

**stall the opponent** (expected `{}` · stall)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{}` · ability-lock, damage-prevention, damage-reduction, item-lock, movement-lock, stall<br>`{}` · stall |
| `gpt-5-mini / low` | `{}` · stall |
| `gpt-5-mini / medium` | `{}` · stall |
| `gpt-5.6-luna / none` | `{}` · stall |
| `gpt-5.6-luna / low` | `{}` · stall |
| `gpt-5.6-luna / medium` | `{}` · stall |

**get pokemon back from the discard pile** (expected `{}` · recovery)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{"category": "Trainer"}` · recovery<br>`{}` · recovery |
| `gpt-5-mini / low` | `{}` · recovery |
| `gpt-5-mini / medium` | `{}` · recovery |
| `gpt-5.6-luna / none` | `{}` · recovery |
| `gpt-5.6-luna / low` | `{}` · recovery |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon"}` · recovery<br>`{}` · recovery |

**stop them from playing items** (expected `{}` · item-lock)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{"category": "Trainer"}` · item-lock |
| `gpt-5-mini / low` | `{}` · item-lock |
| `gpt-5-mini / medium` | `{}` · item-lock |
| `gpt-5.6-luna / none` | `{}` · item-lock |
| `gpt-5.6-luna / low` | `{}` · item-lock |
| `gpt-5.6-luna / medium` | `{}` · item-lock |

**heal my pokemon** (expected `{}` · healing)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{}` · condition-heal, healing<br>`{}` · healing |
| `gpt-5-mini / low` | `{}` · healing |
| `gpt-5-mini / medium` | `{}` · healing |
| `gpt-5.6-luna / none` | `{}` · healing |
| `gpt-5.6-luna / low` | `{}` · healing |
| `gpt-5.6-luna / medium` | `{}` · healing |

**make my opponent discard cards from their hand** (expected `{}` · hand-disruption)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{}` · hand-disruption, mill |
| `gpt-5-mini / low` | `{}` · hand-disruption |
| `gpt-5-mini / medium` | `{}` · hand-disruption |
| `gpt-5.6-luna / none` | `{}` · hand-disruption |
| `gpt-5.6-luna / low` | `{}` · hand-disruption |
| `gpt-5.6-luna / medium` | `{}` · hand-disruption |

**attacker that does more damage for each energy attached** (expected `{}` · damage-scaling)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{}` · damage-scaling |
| `gpt-5-mini / low` | `{"category": "Pokemon"}` · damage-scaling<br>`{}` · damage-scaling |
| `gpt-5-mini / medium` | `{"category": "Pokemon"}` · damage-scaling<br>`{}` · damage-scaling |
| `gpt-5.6-luna / none` | `{}` · damage-scaling |
| `gpt-5.6-luna / low` | `{}` · damage-scaling |
| `gpt-5.6-luna / medium` | `{}` · damage-scaling |

**fire pokemon that search for energy** (expected `{"category": "Pokemon", "types": ["Fire"]}` · energy-search)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{"category": "Pokemon", "types": ["Fire"]}` · energy-search<br>`{"types": ["Fire"]}` · energy-search |
| `gpt-5-mini / low` | `{"category": "Pokemon", "types": ["Fire"]}` · energy-search |
| `gpt-5-mini / medium` | `{"category": "Pokemon", "types": ["Fire"]}` · energy-search |
| `gpt-5.6-luna / none` | `{"category": "Pokemon", "types": ["Fire"]}` · energy-search |
| `gpt-5.6-luna / low` | `{"category": "Pokemon", "types": ["Fire"]}` · energy-search |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon", "types": ["Fire"]}` · energy-search |

**items that search for a pokemon** (expected `{"trainer_type": "Item"}` · search)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{"category": "Trainer", "types": ["Item"], "trainer_type": "Item"}` · search<br>`{"category": "Trainer", "trainer_type": "Item"}` · search |
| `gpt-5-mini / low` | `{"category": "Trainer", "trainer_type": "Item"}` · search |
| `gpt-5-mini / medium` | `{"category": "Trainer", "trainer_type": "Item"}` · search |
| `gpt-5.6-luna / none` | `{"category": "Trainer", "trainer_type": "Item"}` · search |
| `gpt-5.6-luna / low` | `{"category": "Trainer", "trainer_type": "Item"}` · search |
| `gpt-5.6-luna / medium` | `{"category": "Trainer", "trainer_type": "Item"}` · search |

**retreat for free** (expected `{}` · switch)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{"category": "Pokemon", "retreat": {"gte": 0, "lte": 0}}` · switch<br>`{"retreat": {"gte": 0, "lte": 0}}` · switch<br>`{"retreat": {"lte": 0}}` · switch |
| `gpt-5-mini / low` | `{}` · switch |
| `gpt-5-mini / medium` | `{"retreat": {"lte": 0}}` · switch<br>`{}` · switch |
| `gpt-5.6-luna / none` | `{"retreat": {"gte": 0, "lte": 0}}` · (no tags)<br>`{}` · (no tags) |
| `gpt-5.6-luna / low` | `{"retreat": {"gte": 0, "lte": 0}}` · (no tags)<br>`{}` · switch |
| `gpt-5.6-luna / medium` | `{"retreat": {"gte": 0, "lte": 0}}` · (no tags)<br>`{}` · switch<br>`{}` · (no tags) |

**hit their bench for damage** (expected `{}` · snipe)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{}` · snipe, spread<br>`{}` · snipe |
| `gpt-5-mini / low` | `{}` · snipe |
| `gpt-5-mini / medium` | `{}` · snipe |
| `gpt-5.6-luna / none` | `{}` · snipe |
| `gpt-5.6-luna / low` | `{}` · snipe |
| `gpt-5.6-luna / medium` | `{}` · snipe |

**damage all of the opponent's pokemon at once** (expected `{}` · spread)

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{"category": "Pokemon"}` · spread<br>`{}` · spread |
| `gpt-5-mini / low` | `{}` · spread |
| `gpt-5-mini / medium` | `{}` · spread |
| `gpt-5.6-luna / none` | `{}` · spread |
| `gpt-5.6-luna / low` | `{}` · spread |
| `gpt-5.6-luna / medium` | `{}` · spread |

**stadium that punishes ex** (expected `{"trainer_type": "Stadium"}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{"category": "Trainer", "trainer_type": "Stadium"}` · ability-lock, damage-reduction, prize-manipulation<br>`{"category": "Trainer", "trainer_type": "Stadium"}` · counter-placement, damage-reduction<br>`{"category": "Trainer", "trainer_type": "Stadium"}` · prize-manipulation |
| `gpt-5-mini / low` | `{"category": "Trainer", "trainer_type": "Stadium"}` · (no tags) |
| `gpt-5-mini / medium` | `{"category": "Trainer", "trainer_type": "Stadium"}` · (no tags) |
| `gpt-5.6-luna / none` | `{"category": "Trainer", "trainer_type": "Stadium"}` · (no tags) |
| `gpt-5.6-luna / low` | `{"category": "Trainer", "trainer_type": "Stadium"}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"category": "Trainer", "trainer_type": "Stadium"}` · (no tags) |

**big hp basic** (expected `{"stage": "Basic"}` · (no tags))

| Configuration | Distinct outputs across 3 runs |
| --- | --- |
| `gpt-5-mini / minimal` | `{"category": "Pokemon", "hp": {"gte": 150}, "stage": "Basic"}` · (no tags)<br>`{"category": "Pokemon", "hp": {"gte": 200}, "stage": "Basic"}` · (no tags) |
| `gpt-5-mini / low` | `{"category": "Pokemon", "stage": "Basic"}` · (no tags) |
| `gpt-5-mini / medium` | `{"category": "Pokemon", "stage": "Basic"}` · (no tags) |
| `gpt-5.6-luna / none` | `{"category": "Pokemon", "stage": "Basic"}` · (no tags) |
| `gpt-5.6-luna / low` | `{"category": "Pokemon", "stage": "Basic"}` · (no tags) |
| `gpt-5.6-luna / medium` | `{"category": "Pokemon", "stage": "Basic"}` · (no tags)<br>`{"stage": "Basic"}` · (no tags) |

