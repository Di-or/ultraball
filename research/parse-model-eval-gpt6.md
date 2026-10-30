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
