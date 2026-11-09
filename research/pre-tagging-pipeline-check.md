# Pre-tagging pipeline check (2026-11-05)

A last check before tagging the real catalog. Until now the pipeline had only been tested on
hand-written fixtures and on 5–18 hand-picked cards through `scripts/enrich_sample.py`, which
skips Postgres. This run used real TCGdex data all the way through.

## What was run

1. **Existing suites.** `uv run pytest`: 241 passed. Frontend `npm run typecheck` clean,
   `npm test`: 117 passed.
2. **Full-catalog dry run (no model calls).** Every Scarlet & Violet and Mega Evolution era printing
   from TCGdex (29 sets, 4,962 printings) went through the real `project_card` /
   `build_card_identity`, and the real batch request was built for the whole corpus.
3. **Probe tests on real data.** Real TCGdex JSON was fed through `run_ingest` into the test
   Postgres, and the endpoints and pipeline functions were driven from there. Each probe asserted
   the correct behaviour, so a failure is a finding. The probes were throwaway and are not
   committed.
4. **Live end-to-end.** 72 printings (71 dedupe keys), stratified across the cards below, were
   ingested into a throwaway pgvector container. The real `submit_enrichment_batch` →
   `poll_and_apply_batch` ran with `HostedEnrichmentClient`.
   - **Cards in the sample.** The v5/#104 acceptance cards, about 30 format staples, one card per
     energy-symbol letter, the mislabelled Special Energies, a Basic Energy, a name-only card, the
     longest-text card, a vanilla attacker, and the symbol- and wording-drift pairs.
   - **Not finished.** Claude Code stopped the run for low system memory while the batch was in
     flight. The batch's results were read back afterwards, so the tagging side is covered. The
     Voyage embedding pass and the 18 live `/search` queries did **not** run.

## Findings

Every finding below except 14 was reproduced on real data, by a failing probe, the catalog dry
run, or the live batch. 14 is a gap in the code, not a probed failure.

### Blocking: wrong behaviour on real data

| # | Finding | Effect | Where |
|---|---|---|---|
| 1 | TCGdex labels Basic Energy `energyType: "Normal"`; the code checks `"Basic"` | Basic Energy tray empty; Basic Energy never Standard-legal; every deck flagged "56 copies of Fire Energy" + "not Standard-legal"; Basic Energy appears in search; Basic Energy gets submitted for enrichment | `legality.py:24`, `deck_validation.py:53`, `catalog/queries.py:59`, `search/queries.py:56`, parse schema |
| 2 | 14 of 29 Special Energy printings are *also* `"Normal"` (every ME-era one, plus the newest Reversal Energy, `sv04-266`) | `energyType` can't tell basic from special; the Special Energy pill misses them | same; classify by "Energy with no effect text" instead |
| 3 | TCGdex stage is `Stage1` / `Stage2`; `Filters`, the parse schema and the frontend use `"Stage 1"` / `"Stage 2"` | Stage 1 / Stage 2 filters return zero cards | `search/models.py:32`, `parse_client.py:44`, `frontend/src/lib/constants.ts:18`; normalize at projection |
| 4 | A refused / truncated / unparseable answer is stored as `normalized_description = ""`, not NULL; Voyage rejects any empty string (`400 Input cannot contain empty strings`) | One bad card in ~3,000 makes `run_embedding_pass` raise; it commits only at the end, so **no** card gets a vector, and every re-run fails the same way | `pipeline.py` apply step, `queries.get_cards_pending_embedding` |
| 5 | Re-enrichment never clears `vector` (neither the stake-out nor the apply upsert touches it) | After any `PROMPT_VERSION`/`TAXONOMY_VERSION` bump the new description is never re-embedded; search uses stale vectors forever. The semantic path also ranks `pending` rows on their old vector | `pipeline.py` upserts, `search/queries.py` semantic pool |
| 6 | `GET /cards/{entity_id}` takes the `dedupe_key`, and 2,083 of 3,163 real keys contain `/` (attack costs like `[fire/fire]`) | Card detail 404s for 66% of cards, even URL-encoded | `main.py:148` |
| 7 | Card numbers are zero-padded (`localId: "086"`); PTCGL exports write `SVI 86` | Real PTCGL decklists don't import (and `Basic Fire Energy` lines fail via finding 1) | `ptcgl_import.py` / `get_card_by_set_code_and_local_id` |

### Data quality: duplicates, legality, representative printing

| # | Finding | Effect |
|---|---|---|
| 8 | Promo sets carry one series-wide `releaseDate` (`svp` = 2023-03-31, `mep` = 2025-09-26), so the representative-printing order (`release_date desc, ingested_at desc`) ties, and one ingest run gives every printing the same `ingested_at` | The representative depends on ingest order. Paradise Resort's representative was the G printing in one order and legal in the other, so it can drop out of Standard search. 12 entities can show an image-less `mep` printing. Ordering by legality / regulation mark first would fix both |
| 9 | Energy symbols are written three ways (`[R]`, `{R}`, `Fire`), and some reprints have small wording changes | Same card, several entities: duplicate search results and duplicate tagging. Found in Standard: Mega Charizard X ex (`mep-023`/`me02-013`), Delphox (`me04-013`/`mep-074`), Miraidon (`me05-028`/`mep-082`), Golduck (`me02.5-040`/`mep-008`). The errata reconciliation list in CONTEXT.md doesn't exist in code. Expanding symbols to type names in canonical text would fix the first kind, and also helped the model: `mep-023`'s `[R]` became "a specific Energy type" in its description |
| 10 | The newest set, `30th` (2026-09-16), has no regulation marks in TCGdex; its Switch, Ultra Ball and Poké Pad have no rules text; `30th` and `30th-c` both derive set code `30C` | Every 30th printing is non-Standard; name-only cards get tagged from the model's memory (Switch got `switch` from its name alone); PTCGL `30C` lines are ambiguous |
| 11 | Odd regulation marks: `mep-051` Oshawott is `"j"`, `mfb-33`/`mfb-34` are the string `"None"` | Oshawott wrongly non-Standard; uppercase the mark at projection |
| 12 | Rarity is the string `"None"` on 64 printings (`mfb`, `30th-c`); 219 printings have no image (all of `mep`, `sve`, `mee`, part of `svp`) | A "None" rarity facet; blank tiles |
| 13 | Pikachu `svp-101`/`190`/`225` share text but differ in HP (50 vs 70); Reversal Energy and Team Rocket's Energy printings disagree on `energyType` | One entity, arbitrary HP; see findings 1–2 |

### Gaps before a real run

14. **Nothing runs the pipeline on real data yet.** `HostedCatalogClient.fetch_set` raises
    `NotImplementedError`, and no script or job wires `run_ingest` → `submit_enrichment_batch` →
    poll → `run_embedding_pass` against the database. `needs_repair` rows have no repair path.

## Enrichment quality (live batch)

71 / 71 requests succeeded, with no refusals, `max_tokens` stops or invalid tags. $0.100 total, $0.0014 per card.
Per-card output (canonical text, tags, description, rationale, `suggested_new_tag`, output
tokens) is in [`pre-tagging-pipeline-check-raw.json`](pre-tagging-pipeline-check-raw.json), from
batch `msgbatch_01VZWna9pF6UamKKCXHaiRdn` run through the real `_to_result` and validator.

- **Acceptance cards.** 17 / 18 v5/#104 cards got their expected tags (Sinistcha, Dusclops, Gengar
  ex, Lillie's Determination, Judge, Maximum Belt, Defiance Band, Energy Switch, Porygon, Hoppip,
  Toedscruel, Handheld Fan, Roserade, Klawf ex, Azumarill, Brambleghast, Raging Bolt ex).
- **The miss: Kyurem (`sv06.5-047`) got `recoil`, while its own rationale says "recoil does not
  apply".** Toxtricity (`me02-068`) and Gardevoir ex (`sv04.5-029`) both place counters on your
  own Pokémon after attaching, and got opposite `recoil` decisions.
- **Why the model barely reasons.** Output is 86–302 tokens per card (median 180) with
  `effort: high`, so adaptive thinking is barely used. The schema orders `tags` before
  `rationale`, so the rationale is written *after* the tags are chosen and can't inform them.
  Putting `rationale` first in `ENRICHMENT_JSON_SCHEMA` is a cheap fix to try before the real
  run. It is a prompt change, so bump `PROMPT_VERSION`.
- **Staples.** All of them look right: Dragapult ex, Charizard ex, Gardevoir ex, Pidgeot ex, Iono,
  Arven, Professor's Research, Night Stretcher, Super Rod, Prime Catcher, Counter Catcher,
  Artazon, Budew, Buddy-Buddy Poffin, Squawkabilly ex, Unfair Stamp, Neutralization Zone,
  Dusknoir, Terapagos ex, Munkidori, Fezandipiti ex, Hydrapple ex, Archaludon ex, Mega Lucario ex,
  Pecharunt ex.
- **Energy-symbol letters.** All were read correctly, including `{N}` = Dragon (Lillie's Clefairy ex).
- **Number words in descriptions.** No digits leaked. Number words slip through in about 10
  descriptions ("two Colorless Energy", "flip three coins", "quadruple").
- **`suggested_new_tag` signals.** `hp-boost` (Bravery Charm), `tool-lock` (Jamming Tower),
  `attack-lock` (Klefki `me03-059`), `weakness-change` (Lillie's Clefairy ex), `stadium-removal`
  (Pidgeot ex).

## Scale

- **Corpus.** 3,163 unique dedupe keys across SV + ME; 1,958 have a Standard-legal printing.
- **One batch is well within limits.** 24.3 MB and 3,163 requests, against 256 MB / 100,000.
- **Postgres index limit.** The longest key is 691 bytes, under the 2,704-byte btree limit.
- **Cost.** At $0.0014 per card: about $4.50 for everything, about $2.75 for Standard-only.

## Not covered

The live Voyage embedding pass and live `/search` (parse → gate → tag/semantic → RRF) on real
vectors didn't run (see above). Re-run them after findings 1–5 are fixed.

## Corrections (2026-11-08)

Re-checked against the live TCGdex API with caching bypassed (`Cache-Control: no-cache` plus a
cache-busting query parameter), scanning every printing in the 29 sets above plus `me06`.

- **Finding 10 is mostly out of date.** It came from a stale cached API response. `30th` Poké Pad
  (`30th-126`) and Switch (`30th-127`) now have English effect text and regulation marks
  (updated 2026-10-16), and every `30th` printing has a regulation mark. Only Ultra Ball
  (`30th-128`) is still missing English effect text: TCGdex has just the Portuguese text, in the
  source repo as well. Across the other sets in the run, no non-Energy card is missing its text.
- **The ingest has to bypass TCGdex's cache.** A plain request can return a copy that is weeks
  old.
- **New sets arrive partly filled in.** `me06` Delta Reign (released 2026-11-06, not part of this
  run) has 27 Trainers and Special Energies with no English text and no regulation mark on any of
  its 141 cards. `30th` went through the same thing and was filled in about a month after
  release.
- **What was decided.** Sets are ingested only from an explicit list (`me06` stays out until it
  is filled in), and remaining gaps are closed by hand-kept per-printing fixes applied during
  ingest. See CONTEXT.md: Included sets, Catalog override.
- `30th-c` printings have no regulation marks. They are classic reprints, so being treated as
  non-Standard is expected.
