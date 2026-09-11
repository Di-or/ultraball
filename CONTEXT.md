# Ultraball

A conceptual-search Pokémon TCG deckbuilder: describe what a card *does* in natural language and get matching, Standard-legal cards back. This glossary fixes the language the design and code share.

## Language

### Catalog

**Printing**:
A single physical publication of a card in one set — the unit TCGdex returns, identified by its set + number (e.g. `swsh1-178`). The same card reprinted in another set is a *different* printing with its own rarity, art, images, and regulation mark.
_Avoid_: card (when precision matters), variant.

**Card entity**:
The logical card shared across its printings — genuine reprints that play identically collapse to one entity (keyed by `dedupe_key`). Enrichment (tags + embedding) operates on the entity, so identical reprints are tagged and embedded once. Note: the entity is **not** the deck-construction unit — the 4-copy rule operates on the printed **Name** (see below), which is coarser than the entity.
_Avoid_: unique card, oracle card.

**`dedupe_key`**:
The computed `normalize(name + rules_text)` that identifies one unique card entity. It groups genuine reprints, collapses duplicate search hits to one representative, and is the key enrichment runs against (once per unique text, not per printing). Finer than **Name**, which keys on the printed name alone.
_Avoid_: entity id, card hash.

**Name (4-copy key)**:
The full printed `name` string (normalized) — the deck-construction unit for the 4-copy rule, and coarser than `dedupe_key`. Two "Riolu" printings with different attacks are distinct entities but share the name, so they are capped at 4 combined; "Charizard ex" and "Larry's Dunsparce" are distinct names from "Charizard" and "Dunsparce", so 4 each. Basic Energy is exempt.
_Avoid_: card name (when the 4-copy sense matters), title.

**Representative printing**:
The most-recent printing per `dedupe_key` — the single printing the search gate and card display operate on. Most-recent is authoritative, not merely convenient: regulation marks advance monotonically, so the newest printing carries the newest legality, reflects errata, and gives the best image. Distinct-effect cards are already distinct `dedupe_key`s, so this only ever collapses genuine reprints.
_Avoid_: canonical printing, primary printing.

**Catalog layer**:
The abstraction that isolates the rest of the app from TCGdex's shape — the only code that knows TCGdex exists. It ingests printings, keeps a raw snapshot, and projects them into the app's own schema.
_Avoid_: data layer, TCGdex client, importer.

**Errata reconciliation list**:
A curated mapping that unifies printings whose *text* diverges but which the game treats as one card (mostly Trainers corrected by official errata), so they resolve to a single card entity rather than being mistaken for distinct cards.
_Avoid_: errata table, corrections.

**`sub_category`**:
The `{ex, mega, ace-spec}` array derived at ingest from a printing's name and rarity. Encodes **mega ⊂ ex in the data itself** — a Mega card carries `["ex", "mega"]` — so the gate filters it with plain array overlap (§ Candidate pool) and never needs special-case logic to make "ex" also match Mega cards.
_Avoid_: subtype, card tier.

### Legality

**Regulation mark**:
The letter stamped on a card (e.g. `D`, `H`) that TCGdex exposes as `regulationMark`. The primary determinant of Standard legality: cards rotate out by mark.
_Avoid_: block letter, rotation letter.

**Standard-legal**:
Whether a card may be played in the Standard format *right now* — computed by this project from the regulation mark against the current allowed range, minus the ban list, with basic Energy always legal. Not taken from TCGdex's `legal.standard`, which is kept only as a reconciliation signal.
_Avoid_: legal, tournament-legal.

**Basic Energy exception**:
Basic Energy cards are Standard-legal in every rotation regardless of regulation mark, and are exempt from the 4-copy deck rule. Identified by category `Energy` + energy type `Basic`. (Special Energy is *not* basic — it flows through the normal corpus, search, and 4-copy rule.)
_Avoid_: energy exemption.

**Ban list**:
The small, project-maintained set of specific cards disallowed in Standard despite an otherwise-legal regulation mark. An input to the Standard-legal computation.
_Avoid_: banlist, restricted list.

**Rotation**:
The periodic advance of the allowed regulation-mark range that drops the oldest marks from Standard. Handled by editing one config value and re-deriving Standard-legal — never by hand-flipping individual cards.
_Avoid_: format rotation, cutoff change.

### Enrichment

**Functional tag**:
One of the 27 enum-constrained, effects-only labels (in 7 documentation-only families) describing what a card *does* — e.g. `acceleration`, `draw`, `gust`. The shared vocabulary produced by the enrichment pass and emitted query-side by the parser; the user-facing "what it does" layer. Multi-label and versioned by `taxonomy_version`.
_Avoid_: keyword, category, attribute.

**Canonical card text**:
The deterministic, effect-bearing serialization of a card (per `dedupe_key`) that is both the enrichment input and the `dedupe_key` source — one function, so enrichment input and card identity never drift. Keeps names and numbers (the model needs them to reason); excludes flavor text and filter-gate scalars (`hp`/`types`/`retreat`).
_Avoid_: card text, raw text, prompt input.

**Normalized mechanical description**:
The abstractive, identity-and-magnitude-stripped, type-preserving paraphrase of a card's effect that is embedded for semantic search. Strips proper names and numeric magnitudes; keeps game vocabulary and the energy types named *inside* an effect (a Pokémon's own type is stripped — that is a filter-gate attribute). Internal only — never shown to users.
_Avoid_: summary, cleaned text, description.

**Enrichment identity**:
The basis for skipping vs re-running enrichment: `dedupe_key` row presence plus one global `(taxonomy_version, prompt_version)` stamp. Strictly input-based (changed text ⇒ new `dedupe_key` ⇒ auto re-enriched), because temperature-0 output is not bit-deterministic. Legality changes are *not* an enrichment trigger.
_Avoid_: content hash, cache key.

**`card_enrichment`**:
The per-unique-text state table keyed by `dedupe_key`: `tags`, `normalized_description`, `suggested_new_tag`, `rationale`, the version stamps, `status`/`batch_id` (resumability), and the `vector(1024)` embedding. Separate from `cards` because enrichment is once-per-text while `cards` is once-per-printing.
_Avoid_: tags table, embeddings table.

### Quality validation

**Gold set**:
The ~120-card, human-hand-labeled, hard-case-stratified reference set — the ground truth against which both the enrichment taggee and the judge are scored. Over-samples multi-tag cards, slippery families, and `suggested_new_tag` cases, with a few vanilla cards as negative controls.
_Avoid_: test set, sample.

**LLM-as-judge**:
An independent, cross-family stronger model (Claude Sonnet) that re-tags every unique text and rubric-grades the descriptions, feeding the disagreement queue. Cross-family so its errors decorrelate from the GPT-4.1-mini taggee; itself validated against the gold set before being trusted at scale.
_Avoid_: validator, grader, second model.

**Hero set**:
~15–20 iconic cards that must be tagged perfectly — a zero-tolerance ship canary. One miss blocks the ship regardless of aggregate metrics.
_Avoid_: smoke test, examples.

**Judge-trust gate**:
The ≥ 0.90 judge-vs-human agreement threshold on the gold set, below which the judge's at-scale verdicts are not trusted and more cards are hand-reviewed.
_Avoid_: judge threshold.

**Disagreement queue**:
The capped (~50–100), importance-ranked set of enrichment-vs-judge tag disagreements that a human adjudicates — the scarce-human-effort step.
_Avoid_: review queue, conflict list.

**Confusion pair**:
A systematically mislabeled tag pair (e.g. `gust`/`switch`, `draw`/`search`) surfaced by validation; drives tag-definition sharpening and a `prompt_version` bump.
_Avoid_: error pair.

### Retrieval

**Parse object**:
The `{filters, concept, concept_rewritten, tags}` output of the single parse call. `filters` = the closed, enum-enforced hard-gate zone; `concept` = residual natural-language intent (kept for fall-through logging + cache); `concept_rewritten` = the mechanical, card-text-register string that gets embedded; `tags` = query-side functional tags for the tag-match path.
_Avoid_: query object, parsed query.

**Query/passage asymmetry**:
Passages (card descriptions) are embedded `input_type=document` offline; queries are embedded `input_type=query` on the request path. voyage-4 is retrieval-tuned to land the two in the same neighborhood — the mechanism that makes a rewritten concept match real card text.
_Avoid_: query encoding.

**Candidate pool**:
The gated set (`WITH gated`) — the shared universe both retrieval paths rank within. Materialized once from the hard gate so semantic and tag-match see the same admitted cards (RRF is only well-defined over a shared candidate set).
_Avoid_: result set, filtered set.

**Tag-match path**:
The retrieval path that ranks pool cards by query-tag overlap count (any-of, require ≥ 1), not Jaccard (which would penalize richly-tagged staples). Precise on anticipated concepts; goes quiet on un-tagged ones, letting semantic carry them.
_Avoid_: tag search, tag filter.

**RRF merge**:
Equal-weight Reciprocal Rank Fusion (`score = Σ 1/(60 + rank)`) combining the semantic and tag-match paths by rank position only — no score normalization across the two incomparable scales. Final tie-break: cosine distance ascending, then `dedupe_key`.
_Avoid_: score blending, weighted merge.

**Matched signals**:
The per-result structural provenance exposed to the UI — `matched.tags` (which query tags the card carries) and `matched.semantic` (whether the vector path surfaced it). Nearly free from the merge; makes conceptual search legible. Not the cut per-result LLM "why it matched" explanation.
_Avoid_: match reason, explanation.

**Faceted mode**:
The empty-concept-and-empty-tags path: the gate only, no ranking, sorted name A→Z. A plain conventional browse — the same components as conceptual search with the concept path turned off.
_Avoid_: browse mode, filter-only search.

### Frontend

**Filter panel**:
The standing, always-usable structured-filter controls (Type, Stage, HP, category, plus UI-only `regulation_mark`/`rarity` facets). One shared filter state that the natural-language query writes into (parse ticks the controls on) and the user can also edit directly.
_Avoid_: sidebar, facets panel.

**Concept indicator**:
The distinct, removable UI element for the semantic/tag component of a query — the part no structured control can express. Removing it drops semantic ranking and falls back to pure filter/browse; pairs with the per-result matched-signals chip.
_Avoid_: search chip, concept tag.

**Deck panel**:
The always-visible live decklist (grouped Pokémon / Trainer / Energy rows with steppers) plus a readout header (count `n/60`, P·T·E tallies, legality light, violations) driven entirely by the debounced server-side `validate` report — no rules logic on the client.
_Avoid_: deck sidebar, cart.

**Basic-Energy tray**:
The fixed, uncapped, always-legal basic-Energy palette (~11 types) docked near the deck panel, outside the searchable enriched corpus. Click to add; never flagged. Distinct from Special Energy, which lives in the normal corpus.
_Avoid_: energy picker, energy list.
