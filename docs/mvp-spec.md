# Ultraball — Build-Ready MVP Spec

A conceptual-search Pokémon TCG deckbuilder. The user describes what a card *does* in natural language ("energy acceleration under 130 HP, Standard-legal") and gets back matching, Standard-legal cards. Conceptual search is the headline feature; it is layered on top of a competent conventional deckbuilder (filters, keyword, deck construction, legality checking).

> **Status: this is the spec.** It consolidates every load-bearing design decision from the [wayfinder map](https://github.com/Di-or/ultraball/issues/1) (tickets #2–#11), all resolved and interview-defensible. Implementation can begin with no open "how should this work?" questions. The provisional reasoning that seeded it lives in `pokemon-deckbuilder-context-upd.md`; where this spec and the brief disagree, **this spec wins** (the brief predates the corpus-narrowing and several locked decisions).
>
> **Audience:** the implementing engineer. Each section states *what to build* and cites the deciding ticket for the *why*.

---

## 0. Table of contents

1. [Product thesis & success criteria](#1-product-thesis--success-criteria)
2. [Locked stack & scope](#2-locked-stack--scope)
3. [Architecture at a glance](#3-architecture-at-a-glance)
4. [Catalog layer & core schema (#4)](#4-catalog-layer--core-schema-4)
5. [Functional-tag taxonomy (#2)](#5-functional-tag-taxonomy-2)
6. [Hosted model selection (#3)](#6-hosted-model-selection-3)
7. [Offline enrichment pipeline (#5)](#7-offline-enrichment-pipeline-5)
8. [Enrichment quality validation (#6)](#8-enrichment-quality-validation-6)
9. [Request path — parse & concept rewrite (#8)](#9-request-path--parse--concept-rewrite-8)
10. [Request path — semantic search & vector storage (#7)](#10-request-path--semantic-search--vector-storage-7)
11. [Request path — retrieval merge & filter gate (#9)](#11-request-path--retrieval-merge--filter-gate-9)
12. [Deckbuilder shell & Standard legality engine (#10)](#12-deckbuilder-shell--standard-legality-engine-10)
13. [Frontend UX flow (#11)](#13-frontend-ux-flow-11)
14. [Consolidated API contract](#14-consolidated-api-contract)
15. [Database schema summary](#15-database-schema-summary)
16. [Glossary (domain model)](#16-glossary-domain-model)
17. [Out of scope & fog](#17-out-of-scope--fog)
18. [Suggested build sequencing](#18-suggested-build-sequencing)
19. [Handoff notes](#19-handoff-notes)

---

## 1. Product thesis & success criteria

- **The differentiator:** conceptual search over what a card *does*. Every other deckbuilder does keyword + facets only; that gap is the entire product thesis.
- **Table stakes:** it must also be a competent normal deckbuilder — conventional filters/keyword, deck construction, Standard legality. The filter machinery is shared: a plain faceted search is the same components with the concept path turned off.
- **Success criterion:** an **interview-defensible design** (every architectural box explainable end to end) that also produces a **demoable tool**. Portfolio/resume project for a new-grad SWE targeting Python SWE, ML/AI, and data-engineering roles.
- **One-sentence hook:** *"I built hybrid semantic search over a domain-specific corpus, where a single offline enrichment pass produces both a curated tag layer and the embeddings, and query-time results merge via reciprocal rank fusion."*

---

## 2. Locked stack & scope

**Settled scaffolding — not up for re-decision:**

| Area | Decision |
|---|---|
| Backend | **Postgres + pgvector + FastAPI**, single-node Docker for the MVP |
| Catalog source | **TCGdex** (keyless, no auth, V2 REST + official Python SDK), behind an abstracted + cached catalog layer |
| Request-path architecture | **parse → hard filter gate → [tag match ∥ semantic search] → Reciprocal Rank Fusion → ranked list.** No long autoregressive generation in the hot path |
| Enrichment | **one offline pass per unique card text emits BOTH** functional tags and the normalized mechanical description (tags → tag layer; description → embedding) |
| Model hosting | **hosted APIs** for parse, enrichment, embeddings (specific picks in §6) |
| Delivery | a **browser-based web application** — FastAPI backend + a **thin-but-real React single-page frontend**, scoped to what makes search demoable |
| Corpus & format | searchable catalog = **Scarlet & Violet base (SV1) through the current sets (Mega Evolution era, e.g. Pitch Black), growing** as new sets release; **pre-SV1 excluded entirely**. Legality + format filter still handle **Standard only** (a rotating sub-window inside the SV1-onward corpus) |
| Legality | **rules-accurate for Standard** (60-card decks, 4-copy rule with the basic-Energy exception, current ban/rotation list) |

**Corpus size note:** SV1→present is roughly **~5–6k printings** and fewer unique `dedupe_key`s — *not* the ~18k figure from the original brief. This makes the exact-scan vector search (§10) and one-shot quality validation (§8) comfortably safe, and one-time enrichment cheaper than the brief's ~$5–8 estimate.

---

## 3. Architecture at a glance

```
                        OFFLINE (once per unique card text)
  TCGdex ──► catalog layer ──► cards (typed) ──► canonical_card_text
                 │                                      │
              raw_cards                    one GPT-4.1-mini Batch call (temp 0, strict)
                                                        │
                                     { normalized_description, tags[], suggested_new_tag, rationale }
                                                        │
                                      ┌─────────────────┴───────────────────┐
                                   tags[]                          normalized_description
                                      │                                      │
                                 tag layer                          voyage-4 (input_type=document)
                                      │                                      │
                                      └──────────► card_enrichment ◄─────── vector(1024)
                                     (per dedupe_key: tags, description, vector, versions, status)


                        REQUEST PATH (hot; sub-second; no long generation)
  user query
    └► parse & rewrite  (one GPT-5-mini call, strict JSON, temp 0)
          └► { filters, concept, concept_rewritten, tags }
                ├─ filters ─────────────► hard gate (one shared candidate pool CTE)
                │                                │
                │                     ┌──────────┴──────────┐
                │                semantic path          tag-match path
                │        (voyage-4 input_type=query,   (query tags ∩ card tags,
                │         cosine <=> over pool, k=200)   overlap count, ≥1, cap 200)
                │                     └──────────┬──────────┘
                │                     equal-weight RRF (Σ 1/(60+rank))
                │                                │
                └─ concept_rewritten ────────────┘
                                    ranked, paginated list (limit/offset)
```

Design invariants (source brief §3, ratified across #7–#9):

- **Filter gate runs before retrieval.** Legality/HP are *hard* constraints; "acceleration" is a *soft* preference. Pre-filtering guarantees ranking only ever reorders valid cards — correctness never competes with relevance.
- **Two parallel retrieval paths, because they fail in opposite directions.** Tags = precision on anticipated concepts, blind to un-tagged ones; semantic = recall on the long tail, fuzzy on context. For an un-tagged concept the tag path goes quiet and semantic carries it — graceful degradation as structure, not special-case code.
- **RRF merges the two.** They produce scores on incomparable scales (tag-overlap count vs cosine distance); RRF scores by rank position only, so no fake normalization.
- **No long autoregressive generation in the hot path.** The parse call is tiny + cached; the query embedding is one forward pass. This is also why per-result "why it matched" LLM explanations were cut.

---

## 4. Catalog layer & core schema (#4)

Resolved in [Design the catalog layer and core card schema](https://github.com/Di-or/ultraball/issues/4). TCGdex V2 is keyless, no published rate limit ("be considerate + cache"); `image` is a base URL you suffix (`/high.webp`, `/low.webp`).

### 4.1 Card identity — printing-as-row + `dedupe_key`

- Primary `cards` table = **one row per printing**, PK = TCGdex `id` (e.g. `swsh1-178`). Reprints are separate rows (legality, regulation mark, rarity, images all live on the printing).
- Each row carries a computed **`dedupe_key`** = `normalize(name + rules_text)`. It (i) groups reprints for the 4-copy rule display, (ii) collapses duplicate search hits to one representative, (iii) keys **enrichment**, which runs **once per unique text, not per printing** — this is why enrichment count ≪ printing count.
- **Errata:** reprints legitimately differ per print (Pokémon stats/attacks), so divergent text ⇒ a *new* `dedupe_key` by design, surfacing the divergence at ingest. An **errata reconciliation list** (small user-provided input, like the ban list) maps genuinely-errata'd printings — mostly Trainers — back to one canonical text so they share a `dedupe_key`/enrichment. (The user has an errata document to provide; it feeds the ingest/enrichment dedupe step.)

### 4.2 Nested data — JSONB vs typed columns

- **Typed, indexed columns** for the scalar filterables the hot-path gate uses: `hp int`, `types text[]` (GIN), `retreat int`, `rarity`, `set_id`, `regulation_mark`, `category`, `energy_type`, `is_standard_legal bool` (indexed).
- **JSONB** for variable-arity nested objects we never SQL-filter and only display / feed to enrichment: `attacks`, `abilities`, `weaknesses`, `resistances`, `variants`. A whole card reconstructs in one row read.

### 4.3 Two-layer catalog

`raw_cards` (raw TCGdex JSON per printing) → projected into the typed `cards` table. Raw is the reprocessing source + safety net: re-derive schema/`dedupe_key`/enrichment inputs, or absorb a TCGdex shape change, **without re-hitting the API**. The app + pgvector only ever query the typed table. The **catalog layer** is the only code that knows TCGdex exists.

### 4.4 Legality — TCGdex is advisory, we are authoritative

- **Do NOT store `legal.standard` as an authoritative column.** Store the **primitives**: `regulation_mark`, `set_release_date`, `category`/`energy_type`.
- `is_standard_legal` = `(regulation_mark IN allowed_marks OR basic Energy) AND NOT banned`. Null mark + not-basic-Energy ⇒ `false`. Basic Energy = `category=Energy` + `energy_type=Basic`.
- **Config is the source of truth**, the column is derived. One config value (`STANDARD_LEGAL_MARKS` / min-mark cutoff) drives a materialized, indexed `is_standard_legal` recomputed by a single deterministic `UPDATE`. **Rotation = edit one config value + re-derive**, never per-card hand-flipping.
- TCGdex `legal.standard` survives in `raw_cards` as a **reconciliation signal** — flag any card where our flag disagrees (a data-quality check, §8).

### 4.5 Ingestion & refresh

- **Per-set REST crawl** via the official Python SDK: `/sets` → each set → each card, one-time offline, run politely (serial / lightly concurrent). Scoped to the **SV1-onward set list** (~25–30 sets), not all ~170. The `cards-database` GitHub repo is the documented fallback if the API is down.
- **Refresh = set-driven, no per-card diffing.** Card text is immutable and we own legality, so existing cards never need re-fetching. Refresh = `GET /sets`, pull cards only for **set ids we don't have**; also re-pull a stored set if its `cardCount.total` grew (catches late-added secret rares). Two decoupled triggers: **new set → ingest job**; **rotation → config recompute (zero API calls)**.
- Because the corpus is bounded, **`set_id` is an enumerable set** — the parse schema (§9) enumerates it, regenerated at ingest with a `parse_version` bump when a new set lands.

### 4.6 Derived columns required by the request path

Computed at ingest from the JSONB (additive; do not change identity/legality):

1. **`attack_costs int[]` (GIN-indexed)** — the set of per-attack **total** energy costs (Colorless included) for the card. The `attack_cost {gte,lte}` filter (§9) matches with **any-attack** semantics via range-overlap on this array (attacks live in JSONB and aren't efficiently range-filterable as-is).
2. **`sub_category text[]`** — encodes **mega ⊂ ex** in the data (a Mega card carries `["ex","mega"]`), so filtering `ex` returns Mega-ex cards and filtering `mega` narrows — no special-case gate logic. v1 values: `{ex, mega, ace-spec}`.

### 4.7 Images & IP

Store the TCGdex `image` **base URL**; render `{image}/high.webp` (detail) / `{image}/low.webp` (grid). No local/S3 byte caching in the MVP. Carry the **"unofficial fan project — assets © Nintendo/Creatures/GAME FREAK"** disclaimer.

---

## 5. Functional-tag taxonomy (#2)

Resolved in [Draft the v1 functional-tag taxonomy](https://github.com/Di-or/ultraball/issues/2). **v1 is LOCKED.** Full definitions + example cards: branch [`research/tag-taxonomy`](https://github.com/Di-or/ultraball/tree/research/tag-taxonomy) → `research/tag-taxonomy-v1.md`.

**27 functional-effect tags across 7 families**, flat and enum-constrained, one unified list across all supertypes — the shared vocabulary for both the enrichment pass and the query rewriter.

**Enum (flat, exactly these 27):**
`draw`, `search`, `recovery`, `acceleration`, `energy-search`, `energy-recovery`, `energy-removal`, `spread`, `snipe`, `damage-scaling`, `recoil`, `hand-disruption`, `mill`, `ability-lock`, `item-lock`, `special-condition`, `movement-lock`, `gust`, `switch`, `evolution-accel`, `healing`, `condition-heal`, `damage-reduction`, `damage-prevention`, `counter-damage`, `prize-manipulation`, `stall`

Plus the reserved out-of-band **`suggested_new_tag`** (free text, never in the enum).

**The 7 families are documentation-only** (no stored `category` field in v1).

**Boundary decisions (locked):**
- **Effects only** — no structural attributes (HP/stage/type/supertype/EX-ex-V) in the enum; those stay filter-gate DB fields.
- **No quantitative "power" tags** — raw damage → numeric field + semantic search; vocabulary stays qualitative.
- **`gust`** (drag opponent's Bench up) and **`switch`** (retreat your own) kept split — opposite targets.
- **One unified taxonomy** across Pokémon / Trainer / Energy.
- **Ship all 27;** `suggested_new_tag` + fall-through logging grow v2.

**Contracts:** multi-label · enum-constrained · effects-not-attributes · `suggested_new_tag` escape hatch · versioned (`taxonomy_version` per card ⇒ idempotent re-tag on bump).

---

## 6. Hosted model selection (#3)

Resolved in [Choose hosted models for parse, enrichment, and embeddings](https://github.com/Di-or/ultraball/issues/3). Full findings + primary-source citations: `research/model-selection.md` on branch [`research/model-selection`](https://github.com/Di-or/ultraball/tree/research/model-selection). Prices verified against provider pages 2026-08-28.

| Role | Pick | Rough cost | Fallback |
|---|---|---|---|
| **Parse + rewrite** (per query, strict JSON) | **OpenAI GPT-5-mini** (Structured Outputs / constrained decoding) | $0.25 in / $2.00 out per 1M | Claude Haiku 4.5 |
| **Enrichment** (one-time Batch, temp 0) | **OpenAI GPT-4.1-mini** via Batch API | $0.20 in / $0.80 out per 1M → **a few dollars** one-time for the SV1+ corpus | Claude Haiku 4.5 (Batch) / GPT-5-nano (Batch) |
| **Embedding** (retrieval, query/passage asymmetry) | **Voyage `voyage-4`**, `input_type` query/document | $0.06 per 1M; corpus fits the 200M free tier → **≈ $0** | OpenAI `text-embedding-3-large` / Cohere `embed-v4.0` |

- **Embedding dimensionality: 1024** (voyage-4 default) → pgvector column **`vector(1024)`**.
- **Anthropic-only fallback stack is coherent:** Haiku 4.5 for both LLM roles (structured outputs via `output_config.format` + `strict:true`) + Voyage embeddings (Anthropic ships no embedding model and recommends Voyage). Small determinism/cost tradeoff.

---

## 7. Offline enrichment pipeline (#5)

Resolved in [Design the offline enrichment pipeline](https://github.com/Di-or/ultraball/issues/5).

**The pass at a glance:** `canonical_card_text` (per `dedupe_key`) → **one GPT-4.1-mini Batch call, temp 0, strict Structured Outputs** → `{ normalized_description, tags[], suggested_new_tag, rationale }` → tags land in the tag layer; `normalized_description` is embedded (voyage-4, `input_type=document`) into `vector(1024)`. Runs offline, once per unique card text.

### 7.1 Input — `canonical_card_text`

A deterministic serialization built from the typed row + JSONB: `category`/`subtype`, `name`, `stage`+`evolve_from` (Pokémon), every **ability** (name + full text), every **attack** (name + energy cost + damage + full effect text), and for Trainers `trainer_type` + full rules text. **Excluded:** flavor text, set/rarity/images, and the filter-gate scalars `hp`/`types`/`retreat` (attributes, not effects). The **input keeps names and numbers** (the model needs them to reason); only the *output* description strips them. Fixed field order ⇒ hash-stable. **This is the same canonical assembly that produces `dedupe_key` (§4)** — one function, so enrichment input and card identity never drift.

### 7.2 Output — dual-output schema (four fields)

```json
{
  "normalized_description": "string",       // → voyage-4 embedding
  "tags": ["draw", "acceleration"],         // enum-constrained subset of the 27; may be []
  "suggested_new_tag": null,                // out-of-band free text; never in the enum
  "rationale": "string"                     // audit-only: NOT embedded, NOT in the tag layer
}
```

`rationale` (one short sentence) is ~free in a one-time batch and pays off in taxonomy curation / QA (§8). No per-tag span offsets (brittle, low value). Description and tags are **independent views** of one pass (the description is not the tags reworded).

### 7.3 What "normalized mechanical description" means

**Abstractive** rewrite (same pass, temp 0) into a clean mechanical paraphrase.
- **Strip:** flavor, card/Pokémon **identity** (proper names → role words: "this Pokémon", "a Benched Pokémon", "the opponent's Active"), and **numeric magnitudes** (damage/HP/energy counts).
- **Keep:** the game's structural vocabulary — Active, Bench/Benched, hand, deck, discard pile, prize cards, your/opponent's, the Pokémon/Trainer/Energy categories, Basic/Stage 1/Stage 2.
- **Energy types named inside an effect are KEPT** (e.g. "attach a **Darkness** Energy from the discard pile"). They are mechanical vocabulary (a closed ~11-value set), not identity. Decisive reason: the hard-filter gate only filters a **Pokémon's own type**, never "effects involving Dark energy" — so type-specific energy effects (Dark Patch, Metal Saucer, Mirage Gate) are searchable *only* via the semantic layer, which requires the type in the description. A Pokémon's *own* type stays stripped (that's a filter-gate attribute).
- **Vanilla cards** (plain attacker / basic Energy, no effect) get a bare factual line and empty `tags`.

Example: `Dark Patch: Attach a Darkness Energy from your discard pile to 1 of your Benched Pokémon.` → **"Attach a Darkness Energy from the discard pile to one of your Benched Pokémon."**

*Why keeping the type doesn't cause false matches:* semantic search **ranks, it doesn't admit** — the gate already excluded anything disqualified, so a type token only nudges rank within a valid candidate set. Hybrid + RRF is the safety net.

### 7.4 Prompt & enum enforcement

- **Always inject the 27 one-line tag definitions** into the system prompt (the enum's semantic grounding). **Do not inject the raw rulebook** — the handful of baseline-rule clarifications the tag defs depend on (e.g. "acceleration = attaching Energy *beyond* the normal one-per-turn attachment") are folded into the tag definitions once, at authoring time. The system prompt is **one static, versioned artifact**.
- **Strict Structured Outputs** as the hard guarantee: `response_format: {type:"json_schema", strict:true}`, `tags` typed as an array of the 27-string `enum`. Under strict mode the model **cannot** emit an off-enum tag.
- **Defensive post-retrieval validator:** check `message.refusal` **first**, then assert every tag ∈ enum, dedupe, normalize empties — route any refusal/violation to a small **repair queue** (individual re-submit / Haiku 4.5 fallback). *(Verified against OpenAI docs: Batch API supports strict Structured Outputs; refusals are a separate `message.refusal` field; temp 0 is honored but not bit-deterministic.)*

### 7.5 Enrichment identity & state

- **No per-card content hash.** The `dedupe_key` already fingerprints the card text, so changed text ⇒ new `dedupe_key` ⇒ no matching row ⇒ enriched automatically. Identity = **row presence keyed by `dedupe_key`** + **one global `(taxonomy_version, prompt_version)` stamp**. Because temp 0 is not bit-deterministic, identity is strictly **input-based** (skip when unchanged; never re-run and diff outputs).
- State lives in a dedicated **`card_enrichment` table keyed by `dedupe_key`** (one row per unique text): `tags text[]`, `normalized_description`, `suggested_new_tag`, `rationale`, `taxonomy_version`, `prompt_version`, `status`, `batch_id`, `embedding_status`, `updated_at`, and the `vector(1024)`.

### 7.6 The run (incremental + resumable)

1. **Diff** → the `dedupe_key`s with no current row (new cards), or all rows if the global stamp changed.
2. **LLM stage** → build the Batch `.jsonl` for exactly that set; upload, submit, store `batch_id`, mark `submitted`. Poll → retrieve → validate → upsert + mark `done`; failures → repair queue.
3. **Embedding stage** (decoupled) → once a description lands, embed via voyage-4 `input_type=document` and set `embedding_status=done`, so an embedding hiccup never discards a good LLM result.

Resumability falls out of `(status, batch_id, presence)`. **The only re-tag triggers:** (a) new set / new cards → incremental; (b) taxonomy or prompt/model change → global stamp bump → full re-pass; (c) retry of `failed` rows. **Not** legality (legality isn't an enrichment input).

---

## 8. Enrichment quality validation (#6)

Resolved in [Define the enrichment quality-validation approach](https://github.com/Di-or/ultraball/issues/6). This sets the **quality bar**; §7 set the mechanism. End-to-end *retrieval* eval is not owned here (a hero-query smoke test is noted as fog toward the search layer).

**The approach:** an **independent-judge** validation, **anchored to a human gold set**, run as a **one-time acceptance gate** on the initial corpus (blocks the demo if it fails) and re-run as a lightweight **per-set spot-check** when new sets drop. Not a live dashboard.

- **Judge = Claude Sonnet** — cross-family vs the GPT-4.1-mini taggee (decorrelated errors), materially stronger, Sonnet-tier not Opus (cost), cheap enough to run over the whole unique-text corpus once. It does two jobs: **re-tag independently** (feeding the disagreement queue) and **rubric-grade** the descriptions.
- **Gold set (~120 cards):** hand-labeled by the domain expert, over-sampling hard cases — across supertypes; multi-tag cards; cards where the model set `suggested_new_tag`; slippery families (`gust`/`switch`, mill, recovery, disruption); plus a few **vanilla cards as negative controls** (must come back empty). This is where "true" F1 is computed, scoring **both** taggee and judge (which also validates the judge).
- **Disagreement queue:** a capped (~50–100), importance-ranked set of enrichment-vs-judge disagreements a human adjudicates.

**Acceptance bar:**
- Tags: micro-averaged **F1 on the gold set ≥ 0.90 (preferred)**; **ship floor 0.85**, accepted only after the bounded re-pass cycles fail to reach 0.90 without significant redesign.
- **Recall floor 0.80** per high-importance tag (don't silently lose a whole concept).
- **Hero set** (~15–20 iconic cards — Boss's Orders→`gust`, Professor's Research→`draw`, Dark Patch→`acceleration` + Darkness kept in the description, Iono, Arven) must be **perfect**; one miss blocks the ship — a zero-tolerance canary.
- **Description rubric:** ≥ **90%** of judged descriptions pass all checks (identity stripped? magnitudes stripped? game vocabulary kept? energy-types-in-effects kept?).
- **Judge-trust gate:** judge-vs-human agreement on the gold set ≥ **0.90**, else hand-review more before trusting the judge at scale.

**Feedback loop** (each lands as a version bump from §7; bounded to **1–2 re-pass cycles**, then lock v1):
1. Confusion pairs (systematic mislabels) → sharpen tag defs / few-shot → **`prompt_version` bump** → full re-pass.
2. `suggested_new_tag` clusters (recurring, review-surviving) → candidate for **taxonomy v2** → **`taxonomy_version` bump**.
3. Systematic rubric failures → prompt fix → **`prompt_version` bump**.

---

## 9. Request path — parse & concept rewrite (#8)

Resolved in [Design query parse and concept rewrite](https://github.com/Di-or/ultraball/issues/8). **One GPT-5-mini call** (`response_format: json_schema`, `strict:true`, **temperature 0**) turns the raw query into one structured object. No second round trip — the concept rewrite happens in the same call. Memoized (see cache); never does long autoregressive generation.

### 9.1 Output contract (the parse → gate/semantic interface)

```jsonc
{
  filters: {
    format?: "standard",                       // DEFAULTS to standard
    category?: "Pokemon" | "Trainer" | "Energy",
    sub_category?: ("ex" | "mega" | "ace-spec")[],  // multi-valued; mega ⊂ ex → a Mega card is ["ex","mega"]
    types?: string[],                          // enum-enforced (11 SV types), any-of match
    hp?: { gte?: int, lte?: int },
    retreat?: { gte?: int, lte?: int },
    attack_cost?: { gte?: int, lte?: int },    // ANY-attack: some attack's total energy cost in range
    stage?: "Basic" | "Stage1" | "Stage2",
    trainer_type?: "Item" | "Supporter" | "Stadium" | "Tool",
    energy_type?: string,                       // enum-enforced
    set_id?: string                             // enum-enforced: ALL SV1→present set ids, regenerated at ingest
  },
  concept: string,            // residual NL intent; kept for fall-through logging + cache basis
  concept_rewritten: string,  // mechanical, card-text register → embedded (§10)
  tags: string[]              // query-side tags from the 27-tag enum → tag-match path (§11)
}
```

**Consumers:** `filters` → hard gate (§11) · `concept_rewritten` → query embedding (§10) · `tags` → tag-match path (§11) · `concept` → fall-through log + cache.

### 9.2 Filters zone

- **Closed zone, positive-only** — no negation in v1 ("non-ex", "no Rule Box" fall through to `concept`).
- Numerics (`hp`, `retreat`, `attack_cost`) as `{gte,lte}` **range objects** — handle under/over/between with no operator enum, map straight to SQL. `attack_cost` = **any-attack** semantics.
- `types` and `sub_category` are **arrays**, any-of/overlap. `sub_category` encodes mega ⊂ ex in the data.
- **UI-facet-only (not in the parse schema):** `regulation_mark` and `rarity` — with SV1+ scope, `regulation_mark` is legality machinery `format` already covers, and neither is common in NL.

### 9.3 Validation

- Every **closed, stable set is enforced at decode time** via inline JSON-schema enums (`format`, `category`, `sub_category`, `types`, `stage`, `trainer_type`, `energy_type`, `set_id`, the 27-tag `tags`) — invalid values become impossible, not merely caught.
- `set_id` is enumerable **because the corpus is bounded**; its enum is regenerated at ingest whenever a new set lands, paired with a `parse_version` bump (which flushes stale parse-cache entries).
- Residual post-parse validation is minimal; policy = **drop the offending filter and log it, never fail the query** — `concept` always survives.

### 9.4 Concept, rewrite, tags

- `concept` is a **single string** (compound intent embeds fine as one vector; `tags` + RRF carry conjunctions).
- Rewrite is **steered, not RAG'd**: the prompt injects the 27-tag taxonomy with one-line defs + **5–8 few-shot examples** pinning the mechanical style (e.g. "acceleration" → "attach extra Energy from deck or hand beyond the one-per-turn attachment"). Phrased in **card-text register** so it lands near real card descriptions at embed time. `tags` (query-side) are emitted here since the taxonomy is already in context.

### 9.5 Defaults, cache, degradation

- **`format` defaults to Standard** when the user is silent. Empty `concept` **and** empty `tags` ⇒ skip both retrieval paths, return the gated set as faceted search.
- **Parse cache** = a **lexical (exact-match) memo of the parse step only** (not results). Key = `normalize(raw query) + parse_version`; value = the whole parse object; TTL effectively infinite (temp 0); entries die on a `parse_version` bump or LRU. Deliberately **not semantic**. Store: a Postgres table keyed by hash (or Redis) — impl detail.
- **Degrade, don't fail.** On parse timeout/error/junk (~3–4s cutoff; target <1s), fall back to treating the raw query as a **keyword search over `name` + the default Standard gate** (no concept path) and surface a soft "showing keyword matches" state — never a 500. Cache hits bypass this.

---

## 10. Request path — semantic search & vector storage (#7)

Resolved in [Design semantic search and vector storage](https://github.com/Di-or/ultraball/issues/7).

**The path:** `concept_rewritten` → **voyage-4 `input_type=query`** → query vector (cached) → **one SQL statement** (gate `WHERE` + `ORDER BY embedding <=> :q LIMIT 200` over the **representative-printing** set) → ranked `{dedupe_key, representative_printing_id, distance, rank}` → the semantic path into RRF (§11). Exact scan, no ANN index.

### 10.1 The grain mismatch → representative printing

The embedding lives on `card_enrichment`, keyed by `dedupe_key` (one row per unique text). The gate + legality are per-printing columns on `cards`. Resolution:

- **`dedupe_key` already separates the cases correctly.** Two printings with *different* effects/stats have different text ⇒ different `dedupe_key` ⇒ separate results (correct — they play differently). Only identical name+text (genuine reprints, mostly Trainers) share a `dedupe_key`.
- **Searchable unit = the most-recent printing per `dedupe_key` (the representative printing).** Most-recent is *correct*, not just convenient: regulation marks advance monotonically, so the newest printing carries the newest mark ⇒ if even it isn't Standard-legal, no printing is. It also reflects errata and gives the best image.
- **Net: the grain mismatch dissolves.** Gate runs on the representative's columns; NN runs over its one embedding; **no per-query `DISTINCT` needed**.
- **Edge-case guard:** `dedupe_key` excludes the gate scalars `hp`/`types`/`retreat`, so in principle two printings could share a `dedupe_key` yet differ on a gate scalar. Add a **cheap ingest-time assertion that flags any `dedupe_key` whose printings disagree on a gate scalar** (expected empty; if it fires, split that `dedupe_key`). Owned by ingest (§4/§7).

### 10.2 Retrieval params

- **k = 200** candidate depth (not final count) — the fused ranking is what gets paginated. Generous because the exact scan ranks the whole filtered set for free (`LIMIT` is pure truncation) and RRF `1/(60+rank)` makes anything past ~rank 200 numerically dead weight. If the filtered set is smaller than 200, take all of it.
- **Cosine distance via `<=>`**, stored as plain **`vector(1024)`** float32 on `card_enrichment` (voyage-4 returns L2-normalized embeddings). **Quantization (int8/binary/halfvec) deliberately rejected** — the post-filter corpus is a few thousand unique texts (a few MB float32); quantization buys nothing and costs recall.
- **Query embedding + cache:** embed `concept_rewritten` with `input_type=query` (vs `document` offline — the **query/passage asymmetry** *is* the mechanism). **Cache keyed on `normalize(concept_rewritten) + embed_model_version`** — distinct from §9's lexical parse cache, so two raw queries that rewrite to the same concept share one vector. **Empty `concept` ⇒ skip the semantic path entirely** (never a phantom zero-vector search).

### 10.3 Index — exact (flat) scan, no ANN

No ANN index for the MVP. Rationale (locked, interview-defensible):
1. The gate pre-filters to a few thousand legal representatives; **exact cosine over that set is single-digit milliseconds.**
2. HNSW is the *wrong* tool **because of the hard filter**: pgvector applies the ANN graph then filters, so a restrictive gate can make the graph return mostly filtered-out neighbors and **under-fill `k`** (the filtered-ANN under-return problem). `iterative_scan` mitigates but adds tuning surface for zero MVP benefit.
3. **Revisit threshold: HNSW only if the unique-text corpus reaches hundreds of thousands** (multi-game expansion), and even then paired with pre-filter-aware iterative scan.

*(Representative selection may be a per-query `LATERAL` picking the newest printing, or a precomputed materialized `representative_printing` mapping at ingest — equivalent, an implementation choice for the catalog layer.)*

---

## 11. Request path — retrieval merge & filter gate (#9)

Resolved in [Design the retrieval merge and filter gate](https://github.com/Di-or/ultraball/issues/9). This owns everything from the gate SQL to the ranked list the frontend renders.

**The hot path:** `parse output → one shared gated candidate pool (CTE) → [semantic ∥ tag-match, ranked within the pool] → equal-weight RRF → limit/offset ranked list`. No per-query DISTINCT, no score normalization.

### 11.1 One shared candidate pool

The hard gate is materialized **once** as a CTE; both paths rank *within that identical admitted set* (RRF is only well-defined over a shared candidate set):

```sql
WITH gated AS (
  SELECT p.*, e.vector, e.tags
  FROM representative_printing p          -- newest printing per dedupe_key (§10)
  JOIN card_enrichment e USING (dedupe_key)
  WHERE <gate predicates>                 -- see 11.2
)
-- semantic: SELECT dedupe_key FROM gated ORDER BY vector <=> :q LIMIT 200
-- tag:      SELECT dedupe_key, tag_overlap FROM gated WHERE tag_overlap >= 1
--           ORDER BY tag_overlap DESC LIMIT 200
```

### 11.2 Gate predicates

- **Format = Standard** (parse default) ⇒ `is_standard_legal = true` — non-legal cards excluded **pre-ranking**.
- **Filters conjoin (AND) across fields; disjoin (OR) within a multi-valued field.** `"Fire or Water Basics under 130 HP"` → `(types && '{Fire,Water}') AND stage='Basic' AND hp <= 130 AND is_standard_legal`.
- Field → predicate:
  - `category`, `stage`, `trainer_type`, `energy_type`, `set_id` → scalar `=`.
  - `types[]`, `sub_category[]` → array **overlap** (`&&`), any-of. `sub_category` overlap encodes mega ⊂ ex.
  - `hp`, `retreat` `{gte,lte}` → `BETWEEN`/`>=`/`<=`.
  - `attack_cost {gte,lte}` → **any-attack** overlap on `attack_costs int[]`: `EXISTS (SELECT 1 FROM unnest(attack_costs) c WHERE c BETWEEN :gte AND :lte)`.
- **Empty gate ⇒ empty result** (`total: 0`), not an error.

### 11.3 Tag-match path

- **Any-of, ranked by overlap count, require ≥ 1.** `tag_overlap = cardinality(query_tags & entity_tags)`.
- **Overlap count, not Jaccard** — Jaccard penalizes richly-tagged staples; RRF only needs order.
- Equal-overlap cards **share a rank** (competition ranking); the semantic path and tie-breaks separate them. Cap 200.

### 11.4 RRF merge

- **`score(card) = Σ_paths 1/(k + rank)`, k = 60, equal weight, no normalization.** A card in only one path contributes exactly one term — no penalty, no imputed rank.
- Equal path-weight is the defensible standard; weighting is a later tunable knob.
- **Final tie-break** (equal RRF): **cosine distance ascending**, then **`dedupe_key` ascending** — fully deterministic, so offset pagination is stable.

### 11.5 Path routing

| `concept` | `tags` | paths run | ordering |
|---|---|---|---|
| present | present | semantic ∥ tag → RRF | RRF score |
| present | empty | semantic only | cosine asc |
| empty | present | tag only | overlap count desc (equal → set release date desc, then `dedupe_key`) |
| empty | empty | **none — faceted** | **name A→Z, then `dedupe_key`** |

### 11.6 Output contract (the search-side frontend interface)

```jsonc
{
  "results": [
    {
      "entity_id": "<dedupe_key>",      // logical card — the unit displayed
      "printing_id": "sv3-125",         // representative (newest) printing shown
      "name": "Dark Patch",
      "image": "https://.../sv3-125.png",
      "category": "Trainer",            // Pokemon | Trainer | Energy
      "hp": null,
      "types": [],
      "stage": null,
      "regulation_mark": "H",
      "set": { "id": "sv3", "name": "Obsidian Flames" },
      "is_standard_legal": true,        // always true post-gate, explicit
      "rank": 4,
      "rrf_score": 0.0312,
      "matched": {                      // structural provenance from the merge
        "tags": ["acceleration"],       // which query tags this card carries
        "semantic": true                // did the concept/vector path surface it
      }
    }
  ],
  "total": 87,     // ranked-union size (≤ ~400); in faceted mode = full gate size
  "limit": 30,
  "offset": 0
}
```

- **`matched` block** is nearly free (the merge already knows each card's source path + overlapping tags) and makes conceptual search *legible* — a "matched: *acceleration*, +semantic" chip. Structural provenance, **not** the cut per-result LLM explanation.
- **`total`:** where a path ran, = size of the ranked candidate union (distinct cards actually scored, ≤ ~400). **Faceted mode:** no cap, = full gate size.
- **Pagination = `limit`/`offset` + `total`** — the candidate union is small, bounded, deterministically ordered, so offset paging is stable; cursors buy nothing at this scale.

**No new schema required** by the merge — it consumes `is_standard_legal`, `attack_costs int[]`, the representative-printing view, and `vector`/`tags` on `card_enrichment`.

---

## 12. Deckbuilder shell & Standard legality engine (#10)

Resolved in [Design the deckbuilder shell and Standard legality engine](https://github.com/Di-or/ultraball/issues/10).

### 12.1 Deck data model

- A deck is a list of entries `{printing_id, count}` — entries reference **printings** (specific TCGdex id), so art + regulation mark render correctly and PTCGL round-trips. Adding from search adds the representative printing; import adds the exact printing.
- The deck is **client-side, ephemeral React state** for the MVP; persistence stays in the fog.

### 12.2 The two grouping keys (domain-model correction)

The 4-copy rule does **NOT** operate on the card entity. It groups by the **full printed `name` string**:
- Two Standard-legal "Riolu" with different attacks = different `dedupe_key`s (correctly distinct for search/enrichment) but **share the name "Riolu" ⇒ capped at 4 combined** (e.g. 2+2).
- "Larry's Dunsparce" ≠ "Dunsparce", "Charizard ex" ≠ "Charizard" — different name strings ⇒ 4 each.
- Confirmed against TCGdex: the `name` field carries the full printed name verbatim (incl. `ex`/owner prefix).

> **This corrects the CONTEXT.md "Card entity" glossary entry** (see §16 and §19), which currently wrongly says the 4-copy rule operates on the entity.

### 12.3 Legality engine — allow-and-flag, full ruleset, server-side

- **Enforcement: allow-and-flag.** The builder accepts any corpus card; a stateless `POST /decks/validate` (printing ids + counts → report) returns `{legal, violations[], counts}`. Continuous validation on deck change. Ban list + rotation config live server-side (one source of truth; no ruleset shipped to JS).
- **Ruleset — all detectable in the SV1+ corpus:**
  1. Exactly **60** cards.
  2. **≤4 per name** (the 4-copy key above); **basic Energy exempt** (`category=Energy & energy_type=Basic`).
  3. Every card **`is_standard_legal`** (§4).
  4. **≥1 Basic Pokémon** (`category=Pokemon & stage=Basic`).
  5. **≤1 ACE SPEC** — detected via `rarity == "ACE SPEC Rare"` (clean TCGdex signal), backed by a small **maintained ACE-SPEC override list** (mirrors the ban-list pattern; no TCGdex boolean flag exists).
  - **Radiant / Prism ≤1 rules dropped** — not Standard-legal now and absent from the SV1+ corpus. Documented N/A, not coded.
- **Card counts** (Pokémon / Trainer / Energy / total) ride in the same validate report.

### 12.4 Card-detail view

Shows the representative printing's full printed info (name, supertype, subtype/stage, HP, types, attacks + costs, abilities, retreat, weakness/resistance, regulation mark, set + number, rarity, image), a **Standard-legal indicator**, the **27 functional tags** (the user-facing "what it does" layer), the **list of all printings** of the entity (pick art / see reprints), and the **`matched` provenance chip** when reached via search. **`normalized_description` stays internal** — a lossy, magnitude-stripped retrieval artifact that would contradict the printed text beside it.

### 12.5 Decklist import / export (PTCGL)

- **One canonical text format: PTCGL.** Strict writer (export always `count Name CODE number`, grouped P/T/E); lenient reader (import prefers exact `(code, number)`, degrades to name-resolution when missing/unresolvable).
- **Set-code resolution auto-derives** from TCGdex `set.abbreviation.official` (= the PTCGL code, e.g. `OBF`→`sv03`), built into a code→set-id index at ingest, plus a small maintained override map for oddballs (basic-Energy set `SVE`, promos `PR-SV`).
- **Import is all-or-nothing on *resolvability*, not legality:** the paste aborts (nothing loaded) only if a line can't be resolved to a real card. A resolvable deck imports even if Standard-illegal / >4 / ≠60 — those surface in the same validation report. Import is never stricter than hand-building.
- **Basic Energy palette:** the ~11 basic Energy types are a fixed, always-addable, always-legal, uncapped tray, separate from the searchable enriched corpus — resolves `SVE` import lines and keeps basic Energy out of the enrichment/embedding path. **Special Energy (Luminous, Jet) are NOT basic** — they flow through the normal corpus, search, and 4-copy rule.

---

## 13. Frontend UX flow (#11)

Resolved in [Design the frontend UX flow and API contract](https://github.com/Di-or/ultraball/issues/11). A **thin-but-real React SPA** whose job is to make conceptual search *legible* to a viewer/interviewer **without** sacrificing the normal deckbuilder filtering experience. Rules logic stays off the client.

### 13.1 Layout — single-screen persistent split view

One page, **no router**. NL search box + results grid in the main column; an **always-visible deck panel** docked right. Seeing a result land in the deck and the legality readout react in the same viewport is the entire demo loop.

### 13.2 Search interaction — standing filter panel + smart box that writes into it

**One filter state, two input methods:**
- **Standing filter panel** (left of results): normal deckbuilder controls — Type, Stage, HP, category, plus the UI-only facets `regulation_mark` / `rarity`. **Fully usable with zero typing.**
- **NL box writes into the visible panel.** Typing "fire basics that accelerate energy under 130 HP" runs parse (§9) and the panel's controls **physically tick themselves on** (Fire checked, Basic checked, HP ≤130) — parse transparency inside familiar controls. Results always match the visible panel state.
- **Concept/tag part gets a distinct indicator.** The semantic component ("accelerate energy") renders as one separate **`concept: … ✕` indicator** above results — removable to drop semantic ranking and fall back to pure filter/browse. Pairs with the per-result `matched` chip.
- **Fresh NL query replaces the panel state** — a new sentence resets the panel; the user tunes from there. No merge/fill-empties.
- **Parse fires only on NL-box submit.** Editing a chip/facet and re-running sends the edited filter state directly, **no re-parse** — once the user touches the panel, the panel *is* the intent.

### 13.3 Card-detail — modal overlay, dedicated fetch

**Modal overlay** over the current screen, openable from **both** a result card and a deck-panel entry, closing back to exactly where you were. Fed by **`GET /cards/{entity_id}`** (keyed on `dedupe_key`): the search payload is deliberately lean (fast grid), so detail fetches its own full record — full printed info + all printings + the 27-tag subset. The `matched` chip is passed in from the existing search result (a property of that search, not re-fetched). `normalized_description` stays internal.

### 13.4 Deck panel — live decklist + validate-fed readout

- **List:** grouped **Pokémon / Trainer / Energy** (mirrors PTCGL grouping), each row `[img] name [− n +]`. Edit counts / remove inline.
- **Adding:** a `+` on each result card adds the representative printing at count 1; adding again or the stepper increments.
- **Readout header:** total `n / 60`, P/T/E tallies, a legality light (green when `legal:true`), an expandable violations list — **all driven by the debounced validate report, nothing computed client-side.**
- **Allow-and-flag steppers:** never hard-block; a 5th copy is allowed and surfaces as a violation, not a disabled button.

### 13.5 Validation round-trip

Each deck change fires a **debounced (~300ms) `POST /decks/validate`**; the report `{legal, counts, violations[]}` is the **single source of truth** for the readout. No duplicated counting logic in the client.

### 13.6 Import / export / basic-Energy palette

- **Import:** a paste box → `POST /decks/import`. On success the returned entries **replace** the current deck. On failure nothing loads and `unresolved_lines[]` is shown. All-or-nothing on resolvability.
- **Export:** a button renders the current deck to PTCGL text **client-side** (strict writer) into a copy-able box — no server call.
- **Basic-Energy tray:** a small always-visible tray (~11 basic types) docked near the deck panel — click to add, uncapped, never flagged.

---

## 14. Consolidated API contract

The single coherent surface the SPA calls (composes #8/#9 + #10 + two frontend-only endpoints):

| Endpoint | Purpose | Request → Response |
|---|---|---|
| `POST /search` | Search / faceted browse | `{query, filters, facets:{regulation_mark?, rarity?}, limit, offset}` → the §11.6 output contract. `query` non-empty ⇒ parse runs server-side, its output **replaces** `filters` for that request; `query` empty + filters set ⇒ faceted-browse mode. |
| `GET /cards/{entity_id}` | Card-detail (modal) | `entity_id` = `dedupe_key` → full printed record + all printings + the card's 27-tag subset. |
| `POST /decks/validate` | Legality readout (debounced) | `{entries:[{printing_id,count}], format:"standard"}` → `{legal, counts:{pokemon,trainer,energy,total}, violations:[{code,message,cards[]}]}`. |
| `POST /decks/import` | PTCGL import (replace) | `{text}` → `{entries[]}` **or** `{error, unresolved_lines[]}` (all-or-nothing on resolvability). |
| `GET /energy/basics` | Basic-Energy palette | → the fixed basic-Energy list (or a bundled client constant). |
| *export* | PTCGL export | **Client-side** strict writer — no endpoint. |

**One filter state on the wire:** `POST /search` carries both the raw NL string (`query`) and the structured panel state (`filters` + `facets`), because the shared-state UI holds parse-seeded filters *and* hand-set facets in one object. Parse runs server-side only when `query` is non-empty.

**No new schema** — the two new endpoints read existing tables/config.

---

## 15. Database schema summary

Postgres + pgvector. Two catalog layers + the enrichment table + config inputs.

```sql
-- Raw snapshot: reprocessing source + safety net (app never queries this directly)
raw_cards(
  id text PRIMARY KEY,               -- TCGdex printing id
  payload jsonb,                     -- raw TCGdex JSON (incl. legal.standard as reconciliation signal)
  ingested_at timestamptz
)

-- Typed catalog: one row per PRINTING
cards(
  id text PRIMARY KEY,               -- TCGdex printing id, e.g. 'swsh1-178'
  dedupe_key text,                   -- normalize(name + rules_text); enrichment/reprint key   [INDEX]
  name text,                         -- full printed name verbatim (4-copy key; incl. 'ex'/owner prefix)
  category text,                     -- Pokemon | Trainer | Energy
  sub_category text[],               -- {ex, mega, ace-spec}; encodes mega ⊂ ex   [derived at ingest]
  hp int,
  types text[],                      -- [GIN]
  retreat int,
  stage text,                        -- Basic | Stage1 | Stage2
  evolve_from text,
  trainer_type text,                 -- Item | Supporter | Stadium | Tool
  energy_type text,                  -- incl. 'Basic' for basic Energy
  rarity text,
  set_id text,                       -- [INDEX]
  set_release_date date,
  regulation_mark text,
  is_standard_legal bool,            -- DERIVED from config; recomputed by one UPDATE   [INDEX]
  attack_costs int[],                -- per-attack total energy costs   [GIN, derived at ingest]
  image_base_url text,
  attacks jsonb, abilities jsonb, weaknesses jsonb, resistances jsonb, variants jsonb,
  dex_ids int[]
)

sets(
  id text PRIMARY KEY, name text, series text, release_date date,
  card_count_total int, logo_url text, symbol_url text
)

-- Enrichment: one row per UNIQUE TEXT (dedupe_key), ≪ printings
card_enrichment(
  dedupe_key text PRIMARY KEY,
  tags text[],                       -- subset of the 27-tag enum
  normalized_description text,       -- embedded; NOT shown to users
  suggested_new_tag text,            -- out-of-band; feeds taxonomy v2
  rationale text,                    -- audit only
  taxonomy_version int,
  prompt_version int,
  status text,                       -- submitted | done | failed
  batch_id text,                     -- OpenAI Batch id (resumability)
  embedding_status text,             -- pending | done
  embedding vector(1024),            -- voyage-4, cosine <=>
  updated_at timestamptz
)
```

**Config inputs (source of truth, edited by hand):** `STANDARD_LEGAL_MARKS` (allowed regulation-mark range), the **ban list**, the **ACE-SPEC override list**, the **errata reconciliation list**, and the **PTCGL set-code override map**.

**Derived / materialized:** `is_standard_legal` (from config), `attack_costs`/`sub_category` (from JSONB at ingest), and optionally a `representative_printing` mapping (newest printing per `dedupe_key`) — else computed per query via `LATERAL`.

**Parse cache:** a Postgres table keyed by hash of `normalize(raw query)+parse_version` → parse object (or Redis). Query-vector cache keyed on `normalize(concept_rewritten)+embed_model_version`.

---

## 16. Glossary (domain model)

The shared language for design and code. Extends the existing `CONTEXT.md` glossary (on branch `worktree-catalog-schema-context`); terms below marked **(new)** are folded in at consolidation, and **Card entity** is **corrected** (§12.2 / §19).

**Printing** — a single publication of a card in one set (TCGdex `id`, e.g. `swsh1-178`); reprints are distinct printings with their own rarity/art/regulation mark.

**Card entity** *(corrected)* — the logical card shared across its printings; genuine reprints collapse to one entity via `dedupe_key`. Enrichment (tags + embedding) operates on the entity. **The 4-copy deck rule does NOT — it operates on the printed `name` string (see below).**

**Name (4-copy key)** *(new)* — the full printed `name` string (normalized). The deck-construction unit for the 4-copy rule — coarser than `dedupe_key` (which also keys on text). Basic Energy is exempt.

**`dedupe_key`** — `normalize(name + rules_text)`; the enrichment / reprint-grouping / representative-printing key. Finer than **Name** (keys on text too).

**Catalog layer** — the abstraction that isolates the app from TCGdex's shape; ingests printings, keeps a raw snapshot, projects them into the app schema.

**Errata reconciliation list** — a curated mapping unifying printings whose text diverges but which the game treats as one card, so they share a `dedupe_key`.

**Regulation mark** — the letter (`D`, `H`) that TCGdex exposes as `regulationMark`; the primary Standard-legality determinant.

**Standard-legal** — whether a card is Standard-playable *right now*, computed by this project from the regulation mark against the config-driven allowed range minus the ban list, basic Energy always legal. Not TCGdex's `legal.standard` (kept only as a reconciliation signal).

**Basic Energy exception** — basic Energy is Standard-legal every rotation and exempt from the 4-copy rule (`category=Energy` + `energy_type=Basic`).

**Ban list / Rotation** — the project-maintained disallowed-cards set; and the periodic advance of the allowed regulation-mark range, handled by editing one config value + re-deriving.

**Canonical card text** *(new)* — the deterministic effect-bearing serialization of a card (per `dedupe_key`) that is both the enrichment input and the `dedupe_key` source.

**Normalized mechanical description** *(new)* — the abstractive, identity-and-magnitude-stripped, type-preserving paraphrase that is embedded for semantic search (internal, never shown).

**Enrichment identity** *(new)* — `dedupe_key` row presence + global `(taxonomy_version, prompt_version)` stamp; the basis for skip/re-run.

**`card_enrichment`** *(new)* — the per-unique-text state table (tags, description, versions, status, vector).

**Gold set / LLM-as-judge / Hero set / Judge-trust gate / Disagreement queue / Confusion pair** *(new)* — the quality-validation vocabulary (§8): the ~120-card human reference; the cross-family Claude-Sonnet judge validated against it; the ~15–20 must-be-perfect iconic cards; the ≥0.90 judge-agreement threshold; the capped human-adjudicated disagreements; a systematically-mislabeled tag pair.

**Representative printing** *(new)* — the most-recent printing per `dedupe_key`; the single unit the search gate + display operate on (newest mark ⇒ authoritative legality, carries errata, best image).

**Query/passage asymmetry** *(new)* — passages embedded `input_type=document` (offline); queries embedded `input_type=query` (request path); voyage-4 is retrieval-tuned to align the two.

**Parse object** *(new)* — the `{filters, concept, concept_rewritten, tags}` output of the single parse call; `concept` = residual NL intent, `concept_rewritten` = the mechanical, card-text-register string that gets embedded.

**Candidate pool** *(new)* — the gated set (`WITH gated`), the shared universe both retrieval paths rank within.

**Tag-match path / RRF merge / Matched signals / Faceted mode** *(new)* — the query-tag-overlap retrieval path (any-of, ≥1); equal-weight Reciprocal Rank Fusion (`Σ 1/(60+rank)`); the per-result structural provenance (`matched.tags`, `matched.semantic`); the empty-concept-and-tags gate-only alphabetical path.

**Filter panel / Concept indicator / Deck panel / Basic-Energy tray** *(new)* — the frontend vocabulary (§13): the standing always-usable structured-filter controls the NL query writes into; the removable UI element for the semantic query component; the always-visible live decklist + validate-fed readout; the fixed uncapped always-legal basic-Energy palette outside the corpus.

---

## 17. Out of scope & fog

**In-scope fog (not built now; may graduate in a future effort):**
- Deck persistence / accounts / saved-deck management.
- Deck stats (energy curve; type / trainer / energy / Pokémon breakdown).
- Query + result caching specifics (result-cache keys, TTLs, invalidation on set updates) — the *parse* cache and *query-vector* cache are specified; a *result* cache is not.
- Fall-through query logging & clustering for taxonomy growth (the brief's v2 story).

**Out of scope (ruled beyond this destination; return only via a fresh effort):**
- Cloud productionization (batch enrichment jobs, RDS / managed Postgres, S3, serverless API).
- Competitive / meta features (Limitless TCG). Pricing (JustTCG).
- Rules Q&A companion (cut). Per-result "why it matched" LLM explanations (cut — regresses sub-second search).
- Non-Standard formats (Expanded / GLC). Non-English cards. **Pre-SV1 cards.**

---

## 18. Suggested build sequencing

Not a locked plan — a dependency-ordered starting point (the design is complete; this is the natural build order).

1. **Catalog layer + schema (§4, §15).** Ingest SV1→present from TCGdex into `raw_cards` → typed `cards`; compute `dedupe_key`, `is_standard_legal`, `attack_costs`, `sub_category`; build the `sets` table + PTCGL code index. Add the ingest-time gate-scalar assertion (§10.1).
2. **Taxonomy artifact (§5).** Finalize the 27-tag system prompt (defs folded in) from `research/tag-taxonomy-v1.md`.
3. **Enrichment pipeline (§7).** `canonical_card_text` builder (shared with `dedupe_key`), Batch call, validator + repair queue, `card_enrichment` upsert, decoupled voyage-4 embed.
4. **Quality gate (§8).** Hand-label the gold set; run the Claude-Sonnet judge; hit the acceptance bar; iterate ≤1–2 re-passes; lock v1.
5. **Request path (§9–§11).** Parse call + cache; query embedding + cache; the gated-pool CTE + semantic/tag paths + RRF; the `/search` output contract.
6. **Deck engine + API (§12, §14).** `/decks/validate`, `/decks/import`, `/cards/{entity_id}`, `/energy/basics`; PTCGL reader/writer; config inputs (ban list, ACE-SPEC overrides, errata list).
7. **Frontend SPA (§13).** Split view, filter panel + NL box shared state, concept indicator, modal detail, live deck panel, import/export, basic-Energy tray.
8. **Demo polish + README figure** (the parse → gate → tag∥semantic → RRF diagram).

---

## 19. Handoff notes

**CONTEXT.md consolidation (the glossary-folding several tickets deferred to here).** The canonical `CONTEXT.md` currently lives **uncommitted-to-main** on branch `worktree-catalog-schema-context`. Two actions when it lands on `main`:
1. **Correct** the **Card entity** entry — it wrongly says "the 4-copy deck rule operates on the entity." Replace with the corrected entity definition + the new **Name (4-copy key)** term (§16, from #10).
2. **Fold in** the new glossary terms marked **(new)** in §16 (from #5, #6, #7, #8, #9, #11). §16 of this spec is the authoritative source list.

**Research assets referenced by this spec (keep or merge to `main`):**
- `research/tag-taxonomy-v1.md` — full tag definitions + example cards (branch `research/tag-taxonomy`).
- `research/model-selection.md` — model picks + primary-source citations (branch `research/model-selection`).

**User-provided inputs the build needs:** the errata reconciliation document (§4.1), and hand-labeling for the ~120-card gold set (§8).

**Where this spec and the source brief disagree, this spec wins** — the brief (`pokemon-deckbuilder-context-upd.md`) is provisional reasoning and predates the SV1+ corpus narrowing, the locked model picks, and the domain corrections.

---

*Consolidated from wayfinder map [#1](https://github.com/Di-or/ultraball/issues/1), tickets #2–#11, via [Consolidate the build-ready MVP spec (#12)](https://github.com/Di-or/ultraball/issues/12). This document is the map's destination artifact: the way is clear, and implementation can begin.*
