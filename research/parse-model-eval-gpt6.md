# Parse model eval: GPT-6 Luna

**Follows:** [Luna vs Haiku 5.5](parse-model-eval-haiku.md), which measured GPT-5.6 Luna, not GPT-6 Luna, and fed [#94](https://github.com/Di-or/ultraball/issues/94).
**Date:** 2026-10-28, against `main` at `2f453d5` (`PARSE_VERSION` v6). Same 89 queries (44 standard, 45 hard), same scoring, 3 runs per query after a warm-up.
**Rerun:** `uv run python -m scripts.parse_model_eval [--prompt rules] --model gpt-6-luna [--model gpt-5.6-luna] [--effort none --effort low] --raw <file>`. Raw calls are in `parse-model-eval-gpt6-*.json`; `--report --raw <file>` re-renders them. Since #94 the rules are in the production prompt and the `rules` variant is gone; see [After #94](#after-94-production-prompt-v7) for the current command.

`gpt-6-luna` costs $0.10 / $0.01 / $0.50 per 1M uncached input / cached input / output tokens, with cache writes at $0.125: half GPT-5.6 Luna's input price and under half its output price. It supports Chat Completions, Structured Outputs and prompt caching, with efforts `none` to `max` (default `medium`), and lists no dated snapshot ([model page](https://developers.openai.com/api/docs/models/gpt-6-luna)).

## Runs

Three sets of runs, 1,876 calls in all, none failed, $0.33:

1. **GPT-6 Luna `low` / `medium` on the production prompt**, side by side with
2. **GPT-6 Luna and GPT-5.6 Luna, `low` / `medium`, with the candidate rules** (`--prompt rules`).
3. **GPT-6 Luna `none` / `low` with the rules**, side by side with GPT-5.6 Luna `low` + rules as the latency reference.

## Results

| Configuration | Run | Standard: filters / tag P / R | Hard: filters / tag P / R | Median std / hard | Within 4s std / hard | Fully right (std, hard) | Wrong every run | $ / 1k std |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| GPT-6 `low` + rules | 2 | 100% / 1.00 / 1.00 | 100% / 1.00 / 1.00 | 2.66s / 3.03s | 90% / 93% | **44/44, 45/45** | 0 | $0.099 |
| GPT-6 `low` + rules | 3 | 99% / 1.00 / 1.00 | 100% / 1.00 / 0.99 | 2.56s / 2.80s | 91% / 93% | 43/44, 44/45 | 0 | $0.098 |
| GPT-6 `medium` + rules | 2 | 98% / 1.00 / 1.00 | 100% / 1.00 / 1.00 | 2.56s / 3.03s | 98% / 89% | 43/44, 45/45 | 0 | $0.109 |
| GPT-6 `none` + rules | 3 | 97% / 1.00 / 1.00 | 95% / 0.95 / 1.00 | 1.43s / 1.54s | 89% / 100% | 42/44, 42/45 | 3 | $0.074 |
| GPT-6 `low` | 1 | 100% / 1.00 / 0.97 | 99% / 1.00 / 1.00 | 2.44s / 2.80s | 98% / 96% | 43/44, 44/45 | 1 | $0.096 |
| GPT-6 `medium` | 1 | 100% / 1.00 / 0.97 | 97% / 0.98 / 1.00 | 2.70s / 3.11s | 93% / 86% | 43/44, 42/45 | 1 | $0.104 |
| GPT-5.6 `low` + rules | 2 | 97% / 0.99 / 1.00 | 99% / 0.98 / 1.00 | 1.95s / 2.08s | 100% / 99% | 42/44, 43/45 | 1 | $0.176 |
| GPT-5.6 `low` + rules | 3 | 96% / 0.99 / 1.00 | 97% / 0.97 / 1.00 | 1.79s / 1.89s | 100% / 100% | 41/44, 42/45 | 2 | $0.174 |
| GPT-5.6 `medium` + rules | 2 | 98% / 1.00 / 1.00 | 99% / 0.99 / 1.00 | 2.08s / 2.48s | 98% / 99% | 43/44, 42/45 | 0 | $0.204 |

"Fully right" counts queries where all 3 runs matched the expected filters and tags exactly. "Wrong every run" counts queries (standard and hard together) missed on all 3 runs. Rows from the same run were measured side by side, so latency is best compared within a run. The full report tables are re-rendered from the raw files with `--report`.

## Findings

**Accuracy: GPT-6 Luna with the rules is the best configuration measured so far.**
- At `low`, it got every one of the 89 queries right on every run in run 2, and 87 of 89 in run 3. Its only slips were one `category: Energy` without `energy_type` on "special energy cards" and one missing tag on "energy denial".
- At `medium` it is no better than `low`.
- Even without the rules, GPT-6 Luna `low` scored 100% / 99% filters. Its one consistent miss is the one the rules fix: "hit their bench for damage" gets `snipe` without `spread`.

**Speed: GPT-6 Luna reasons at `low`, and that costs time.**
- It spends 42–67 reasoning tokens a call at `low`, against GPT-5.6 Luna's ~5. Its median is 2.4–2.8s, about 0.6–0.9s slower than GPT-5.6 Luna `low` measured in the same run.
- 90–98% of its calls finish within 4s, against 99–100% for GPT-5.6 Luna `low`. Under the current 4s timeout, roughly 2–10% of GPT-6 `low` searches would fall back to keyword-only.
- Within 6s, 98–100% finish.
- GPT-6 Luna's slow calls are spread through each run, so this is how it normally performs, not a one-off burst.

**GPT-6 Luna at `none` is fast but less accurate.**
- With no reasoning, its median drops to 1.43s / 1.54s, the fastest Luna measured, at the lowest cost ($0.074 per 1k).
- Accuracy falls to 97% / 95% filters, with 3 queries wrong on every run:
  - "pokemon tools" gets filtered to Pokémon (`category: Pokemon` with `trainer_type: Tool`, which matches nothing);
  - "151 pokemon with free retreat" gets `retreat-reduction` or `switch` instead of the 0-retreat filter;
  - "basic energy acceleration from the discard" adds `energy-recovery`, and on 2 of 3 runs also an `energy_type: Basic` filter. (#94 accepts `energy-recovery` for this query, but not the filter.)
- It also drops the attack-cost filter from "pokemon under 100 hp with free attacks" on 2 of 3 runs.
- All of its calls over 4s were bunched at the start of the run: the warm-up and the first ~28 calls, at 4.6–17s. After that, no call took longer than 4s. That looks like a cold start on OpenAI's side, which production could also hit after a quiet spell, when the prompt cache has expired.

**Cost.** GPT-6 Luna `low` is about $0.10 per 1,000 standard queries, the same as Haiku 5.5 and 45% less than GPT-5.6 Luna `low` ($0.17–0.18).

## The trade-off for #94

| Option | Accuracy | Within 4s | Median | $ / 1k |
| --- | --- | --- | --- | ---: |
| GPT-6 Luna `low` + rules | best (87–89 of 89 fully right) | 90–93% | ~2.6–2.8s | $0.10 |
| GPT-5.6 Luna `low` + rules | 83–85 of 89 fully right | 99–100% | ~1.8–2.0s | $0.17 |
| GPT-6 Luna `none` + rules | 84 of 89 fully right, 3 always wrong | 89–100% (cold-start burst) | ~1.4–1.5s | $0.07 |

Choosing GPT-6 Luna `low` means either accepting that up to ~10% of searches degrade to keyword-only at 4s, or raising the timeout to about 6s.

## After #94: production prompt v7

**Date:** 2026-10-30, against `parse-gpt6-luna` at `26ccf06` (`PARSE_VERSION` v7). Same 89 queries, 3 runs after a warm-up, with #94's expected answers ("under" / "over" exclusive, `tags_also` for "basic energy acceleration from the discard").
**Rerun:** `uv run python -m scripts.parse_model_eval --model gpt-6-luna --effort low --effort medium --raw research/parse-model-eval-gpt6-v7-raw.json`. Pass `--raw`: without it the run overwrites `parse-model-eval-haiku-raw.json`.

#94 moved the four trialled rules into the production prompt, restricted `energy_type` to `Basic` / `Special`, made "under" and "over" exclusive, switched production to GPT-6 Luna at `low`, and raised the timeout to 6s. 536 calls, none failed, $0.06.

| Configuration | Standard: filters / tag P / R | Hard: filters / tag P / R | Median std / hard | Within 4s std / hard | Within 6s std / hard | Fully right (std, hard) | Wrong every run | $ / 1k std |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| GPT-6 `low` (production) | 100% / 1.00 / 1.00 | 99% / 1.00 / 1.00 | 2.37s / 2.69s | 100% / 99% | 100% / 100% | **44/44, 44/45** | 0 | $0.099 |
| GPT-6 `medium` | 100% / 1.00 / 1.00 | 100% / 1.00 / 1.00 | 2.39s / 2.77s | 98% / 95% | 100% / 100% | 44/44, 45/45 | 0 | $0.108 |

**No regression against the `+ rules` rows above.**
- GPT-6 `low` matched its best `+ rules` run: 88 of 89 queries right on every run.
- The one miss was a single run of "stage 2 grass pokemon over 150 hp from Temporal Forces" picking `set_id` `sv06` (Twilight Masquerade) instead of `sv05`. It got the bound right (`hp.gte` 151) on all 3 runs.
- The other two disagreements in the report ("attacker that does more damage…", "big hp basic") are both accepted answers (`filters_also`).

**The targeted fixes held on every run, at both efforts.**
- "special energy cards" returned `category: Energy, energy_type: Special`. The `+ rules` runs had missed `energy_type` once, and before the enum Luna had returned `"Special Energy"` / `"special"`.
- "pokemon under 130 HP with 1 retreat" returned `hp.lte` 129, "pokemon under 100 hp with free attacks" `hp.lte` 99, and "stage 2 grass pokemon over 150 hp…" `hp.gte` 151. The prompt's examples ("under 90 HP", "over 200 HP", "3 retreat or less") deliberately avoid the eval's wording.
- "hit their bench for damage" got `snipe` and `spread`.
- "energy denial", missed once in the `+ rules` runs, got `energy-removal` on every run.

**Latency fits the 6s timeout.** Every GPT-6 `low` call finished within 6s (≥98% required). In this run, 99–100% also finished within 4s, against 90–93% in the `+ rules` runs. Latency varies between runs, so the 6s timeout still leaves headroom for slow periods.

## After #101: taxonomy v4 (`PARSE_VERSION` v8)

**Date:** 2026-11-03, `PARSE_VERSION` v8. 90 queries, 3 runs after a warm-up, GPT-6 Luna at `low` only.
**Rerun:** `uv run python -m scripts.parse_model_eval --model gpt-6-luna --effort low --raw research/parse-model-eval-gpt6-v8-raw.json`.

#101 replaced `snipe` and `spread` with `bench-reach` and `multi-target` (see `tag-taxonomy-v4.md`), and swapped the parse prompt's two Bench rules for three: a plain Bench query is `bench-reach`, hitting several or all is `multi-target`, and naming damage counters adds `counter-placement`. The eval's `counter-placement vs snipe/spread` group became `bench-reach vs multi-target vs counter-placement`, with a new query ("hit one of their benched pokemon"). Four queries outside the group were renamed to the new tags ("…that snipe" ×2, the `gust` confusion, "damage all their pokemon and poison them"). 271 calls, none failed, $0.03.

| Configuration | Standard: filters / tag P / R | Hard: filters / tag P / R | Median std / hard | Within 4s std / hard | Within 6s std / hard | $ / 1k std |
| --- | --- | --- | --- | --- | --- | ---: |
| GPT-6 `low` (production) | 99% / 1.00 / 1.00 | 100% / 1.00 / 1.00 | 1.98s / 2.13s | 99% / 99% | 99% / 100% | $0.094 |

**No tag regression against v7.** Tag precision and recall stay at 1.00 on both rows.

**The Bench group was right on every run.**
- "put damage counters on their bench" → `counter-placement`, `bench-reach`
- "hit their bench for damage" → `bench-reach`
- "hit one of their benched pokemon" → `bench-reach`
- "damage all of the opponent's pokemon at once" → `multi-target`, `bench-reach` (the accepted `tags_also` answer)
- "drag out a benched pokemon and hit it" stayed `gust`

**One filter miss, outside the group.** "pokemon tools" was filtered to `category: Pokemon` on 2 of 3 runs, the same misreading noted for earlier prompts above. It is unrelated to tags.

## After #103: taxonomy v5 (`PARSE_VERSION` v9)

**Date:** 2026-11-04, `PARSE_VERSION` v9. 99 queries (50 standard, 49 hard), 3 runs after a warm-up, GPT-6 Luna at `low` only.
**Rerun:** `uv run python -m scripts.parse_model_eval --model gpt-6-luna --effort low --raw research/parse-model-eval-gpt6-v9-raw.json`.

#103 split `damage-prevention` from `effect-prevention`, added `damage-boost` and `energy-movement`, merged `energy-search` / `energy-recovery` into `search` / `recovery`, and widened `counter-damage` to any punishment of the attacker (see `tag-taxonomy-v5.md`). The eval renamed the three queries that expected the merged tags, and "basic energy acceleration from the discard" now expects `acceleration` + `recovery` with no `tags_also`. Ten queries were added, one or more per new or changed tag and per "carries both" rule, worded unlike the prompts' examples.

Four evals were run, each 3 runs after a warm-up (298-301 calls), none failed, $0.12 in all:

1. **Glossary alone.** Missed two new hard queries: "move the opponent's energy onto their bench" got `energy-movement` without `energy-removal` on all 3 runs, and "both players shuffle their hands and draw new ones" missed `hand-disruption` once.
2. **A hand-written two-tag rule in the parse instructions.** Every new query right on every run; only "pokemon tools" missed.
3. **The shared two-tag table** (`TWO_TAG_RULES`, rendered after the glossary in both prompts) **and the wider `counter-damage`.** Every new and changed query right on every run, but four misses on unchanged queries: "151 pokemon with free retreat" got `retreat-reduction` instead of the 0-retreat filter on 2 runs, "retreat for free" got `switch` once, "cards like Boss's Orders" got no tag once, and "basic energy acceleration from the discard" added an `energy_type: Basic` filter once.
4. **Shipped: as 3, plus "which carries its own tag too" in `counter-damage`.** None of run 3's four misses came back, so they read as run-to-run variance rather than an effect of where the table sits. The raw file holds this run.

| Configuration | Run | Standard: filters / tag P / R | Hard: filters / tag P / R | Median std / hard | Within 4s std / hard | Within 6s std / hard | $ / 1k std |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| GPT-6 `low` (production) | 4 | 99% / 1.00 / 1.00 | 100% / 0.99 / 1.00 | 2.16s / 2.32s | 100% / 100% | 100% / 100% | $0.100 |
| GPT-6 `low` | 3 | 99% / 0.99 / 0.99 | 98% / 0.99 / 0.99 | 2.16s / 2.45s | 99% / 99% | 100% / 100% | $0.097 |

**No tag regression against v8 outside the changed tags.** In run 4 the only tag disagreement is "bench barrier" getting `effect-prevention` alongside `damage-prevention` once. Both are changed tags, and some Bench barriers (Rabsca) do prevent both.

**Every new query was right on every run in runs 3 and 4:**
- "protect my pokemon from damage counters" → `effect-prevention`
- "tools that add damage" → `damage-boost`, `trainer_type: Tool`
- "pokemon that do extra damage to ex" → `damage-boost`, `category: Pokemon`, no `sub_category`
- "move energy to another pokemon" → `energy-movement`
- "move the opponent's energy onto their bench" → `energy-movement`, `energy-removal`
- "attackers that hurt themselves" → `recoil`
- "shuffle hand and draw" → `draw`
- "both players shuffle their hands and draw new ones" → `draw`, `hand-disruption`
- "knock out the attacker when my pokemon gets hit" → `counter-damage`
- "poison the attacker when it hits me" → `counter-damage`, `special-condition`

The renamed queries and "basic energy acceleration from the discard" (`acceleration`, `recovery`) were right on every run of run 4.

**One filter miss, unchanged from v8.** "pokemon tools" was filtered to `category: Pokemon` on 2 of 3 runs.

## After #104: coin flips aren't a count (`PARSE_VERSION` v10)

**Date:** 2026-11-05, `PARSE_VERSION` v10. 101 queries (50 standard, 51 hard), 3 runs after a warm-up, GPT-6 Luna at `low` only.
**Rerun:** `uv run python -m scripts.parse_model_eval --model gpt-6-luna --effort low --raw research/parse-model-eval-gpt6-v10-raw.json`.

#104 added "Coin flips aren't a game-state count." to the `damage-scaling` definition (see `tag-taxonomy-v5.md`). One hard query was added: "attackers that do more damage the more heads they flip" expects no tag (`category: Pokemon` accepted). 304 calls, none failed, $0.03.

| Configuration | Standard: filters / tag P / R | Hard: filters / tag P / R | Median std / hard | Within 4s std / hard | Within 6s std / hard | $ / 1k std |
| --- | --- | --- | --- | --- | --- | ---: |
| GPT-6 `low` (production) | 100% / 1.00 / 1.00 | 100% / 1.00 / 1.00 | 2.76s / 3.27s | 90% / 69% | 100% / 98% | $0.104 |

**No disagreements on any query in any run.** The new query got no tag on all 3 runs, and the three existing `damage-scaling` queries ("more damage for each energy attached", "stronger with more benched pokemon", "hit harder the more damage they have") kept the tag on all 3. "pokemon tools", the one filter miss under v9, was right on every run, which fits it being run-to-run variance.

**Slower than v9.** Medians went from 2.16s / 2.32s to 2.76s / 3.27s, and 2% of hard calls went over 6s. The 6s timeout held on 300 of 303 calls. To separate the change from API latency on the day, v9 (`main` at `1b374ce`) and v10 were then run at the same time, 3 runs each, raw calls not kept. On the 100 shared queries v10's median was 2.51s against v9's 2.22s, v10 was slower on 85 of 100 queries (median +0.27s) and in every run, and neither had a call over 6s. As a control, two copies of v10 were run the same way: one was slower on 51 of 101 queries (median +0.03s), and the faster copy changed from run to run, so the side-by-side setup doesn't make a gap of its own. A second side-by-side v9 / v10 run a few hours later shrank the gap to +0.05s (v10 slower on 59 of 100 queries; run medians 2.43 / 2.50s, 2.24 / 2.40s, 2.26 / 2.27s), close to the control. So the 0.27s gap came from the API at that time, not the prompt, which is only 8 tokens longer, with reasoning tokens unchanged (48 against 46 on average). Any gap left is too small to tell from noise.
