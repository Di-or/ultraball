# Hosted model selection: parse, enrichment, embeddings

**Ticket:** [#3 — Choose hosted models for parse, enrichment, and embeddings](https://github.com/Di-or/ultraball/issues/3)
**Date:** 2026-08-28 (revised 2026-09-30, see below)
**Scope:** Hosted API models (not local) for a Pokémon TCG deckbuilder's conceptual-search system: ~18,000 cards embedded into Postgres + pgvector.

All prices verified against provider primary sources (pricing/docs pages) as cited. Anything I could not tie to a primary source is called out under **Unverified / assumptions** at the end.

---

## Revision 2026-09-30: smaller corpus

The corpus is now scoped to Scarlet & Violet through the current Mega Evolution era, not every card ever released. That is roughly 3.5–4.5k printings, which collapse to an estimated **~2–2.5k `dedupe_key`s** (alt-art and secret-rare reprints share card text). This is an estimate; confirm with `SELECT count(DISTINCT dedupe_key)` after real ingest.

Only work that scales with the corpus is affected:

| Role | Was | Now | Why |
|---|---|---|---|
| Parse + rewrite | GPT-5-mini | **Unchanged** | Cost scales with query volume, not corpus size. The binding constraint is latency (<1s target, 4s timeout), which rules out bigger reasoning models. |
| Enrichment | GPT-4.1-mini (Batch, temp 0) | **Claude Sonnet 5.5** (Message Batches, structured outputs) | ~7–9× fewer cards makes a stronger model cheap, and tag quality is the product. See Role 2. |
| Embedding (documents) | voyage-4 | **voyage-4-large** | Still inside the free tier at this size. |
| Embedding (queries) | voyage-4 | **Unchanged** | voyage-4-series models share one embedding space, so queries stay on the faster standard model. |

**The temperature-0 argument is dropped.** It was the main reason GPT-4.1-mini beat reasoning models, but `CONTEXT.md` (Enrichment identity) already treats temperature-0 output as not bit-deterministic, and re-enrichment is keyed on inputs plus the `(taxonomy_version, prompt_version)` stamp. Determinism was never load-bearing.

**Parse client, temperature removed (#80):** `app/clients/parse_client.py` used to send `"temperature": 0` to `gpt-5-mini`. GPT-5 reasoning models are expected to reject non-default temperature with a 400, so the field was removed. The 400 itself is still unverified against a live call; tests mock the HTTP layer.

---

## TL;DR — the three picks (current)

| Role | Recommendation | Rough cost | Fallback |
|---|---|---|---|
| 1. Parse + rewrite (per query) | **OpenAI GPT-5-mini** (Structured Outputs, strict JSON schema) | $0.25 in / $2.00 out per 1M tok | Claude Haiku 4.5 |
| 2. Enrichment (offline batch, ~2–2.5k cards) | **Claude Sonnet 5.5** via Message Batches, strict structured outputs, adaptive thinking | $1 in / $5 out per 1M tok (batch); **~$10–20 per full run** | OpenAI flagship reasoning model (Batch); also the second tagger for disagreement review |
| 3. Embedding | **Voyage `voyage-4-large`** for documents, **`voyage-4`** for queries, `input_type` document/query | $0.12 / $0.06 per 1M tok; corpus fits inside the 200M free tokens (≈ $0) | OpenAI `text-embedding-3-large` / Cohere `embed-v4.0` |

**Embedding vector dimensionality: 1024** (voyage-4 series default) → pgvector column `vector(1024)`. Unchanged: at this corpus size an exact scan is milliseconds at any dimension, and staying at 1024 avoids a migration.

The original 2026-08-28 analysis follows. Where it conflicts with the revision above, the revision wins.

---

## Role 1 — Parse + rewrite model

**Requirement:** small/cheap, must support structured output / constrained decoding (JSON schema). Splits a natural-language query into structured filters + a rewritten "concept" phrase. One call per user query; latency + cost matter but it's tiny and cacheable.

**Pick: OpenAI GPT-5-mini.**
- One-line justification: OpenAI Structured Outputs does true constrained decoding against a strict JSON schema (guaranteed-valid JSON, not best-effort), and GPT-5-mini has the instruction-following to produce a good rewritten "concept" phrase while staying cheap.
- Cost: **$0.25 / 1M input, $2.00 / 1M output** (standard). Prompt-cached input reads are cheaper, which matters here since the parse system prompt/schema is a stable prefix. [OpenAI pricing]
- Fallback: **Claude Haiku 4.5** — $1.00 / 1M in, $5.00 / 1M out; supports structured outputs via `output_config: {format: {...}}` with `strict: true`. This is the natural Anthropic-aligned choice for the repo's Claude default. [claude-api skill, cached 2026-06-24]

**Cheaper alternative if rewrite quality holds:** GPT-5-nano ($0.05 in / $0.40 out) or GPT-4.1-nano ($0.10 / $0.40) — both support Structured Outputs. Worth an eval; the "concept" rewrite is the part that benefits from the larger mini model.

## Role 2 — Enrichment model

> **Superseded 2026-09-30: Claude Sonnet 5.5.** With ~2–2.5k cards, a stronger model costs about $10–20 per full run, so cost no longer decides this role. Sonnet 5.5 fits the existing seam:
> - **Strict structured outputs** (`output_config.format`) constrain `tags` to the 27-tag enum, as OpenAI strict mode did.
> - **Message Batches** (50% off) match `EnrichmentClient`'s submit / poll / fetch shape. Results come back in any order, keyed by `custom_id` (use the `dedupe_key`).
> - **Request constraints:** a non-default `temperature` returns a 400, thinking is always on and depth is set with `output_config.effort` (default `high`; compare `medium` vs `high` on the gold set), and forced `tool_choice` returns a 400 (use `output_config.format` instead).
> - **Refusals:** check `stop_reason == "refusal"` per result. Server-side fallbacks are not available on Batches, so the repair path handles them.
> - **Billing:** needs a Claude API key with Console credits. A Claude Pro subscription does not cover API usage.
> - **LLM-as-judge flips provider:** `CONTEXT.md` had Claude Sonnet judging a GPT-4.1-mini taggee. With Sonnet as the taggee, the judge becomes an OpenAI flagship reasoning model so the two stay cross-family. At ~2.5k cards the judge can still re-tag every unique text.
>
> Rough cost: ~2.5k cards × (~1,500 in, cached prefix, + ~1,300 out incl. thinking) ≈ 3.75M in + 3.25M out ≈ $3.75 + $16 at batch rates. Re-estimate once the prompt exists.
>
> The original analysis below is kept for history.

**Requirement:** small/cheap, good at multi-label classification + text normalization. Runs ONCE per ~18,000 cards as an offline batch (bounded one-time cost). Temperature-0 determinism wanted.

**Pick: OpenAI GPT-4.1-mini, run through the Batch API at `temperature=0`.**
- One-line justification: it is a non-reasoning model that actually honors `temperature=0` (the determinism the ticket asks for), supports strict Structured Outputs for the multi-label schema, and the offline Batch API halves the price on a one-time job where latency is irrelevant.
- Cost: **$0.20 / 1M input, $0.80 / 1M output** (Batch API, 50% off the $0.40 / $1.60 standard rate). [OpenAI pricing]
- Rough total for 18k cards: assuming ~800 input + ~200 output tokens per card → ~14.4M in + ~3.6M out → ≈ $2.9 + $2.9 ≈ **$5.8**, call it **~$5–8** depending on prompt size. This is a bounded one-time cost.
- Fallback: **Claude Haiku 4.5** via Message Batches (50% off → ~$0.50 / 1M in, $2.50 / 1M out; supports a `temperature` param) for the Anthropic path; or **GPT-5-nano** via Batch ($0.025 / $0.20) if you want the floor on cost and accept that GPT-5 reasoning models don't honor `temperature=0` the way GPT-4.1-mini does.

**Why not GPT-5-nano as primary:** it is cheaper, but the GPT-5 family are reasoning models and do not treat `temperature=0` as a hard determinism guarantee. Since the ticket explicitly wants temp-0 determinism, the non-reasoning GPT-4.1-mini is the more defensible primary; nano stays as the cost-floor fallback.

## Role 3 — Embedding model

**Requirement:** retrieval-tuned, ideally supports query-vs-passage asymmetry. Embeds cleaned card descriptions and rewritten queries for cosine/nearest-neighbor search over ~18k cards in Postgres + pgvector. **Report output dimensionality** (sets the pgvector column).

**Pick: Voyage AI `voyage-4`.**
- One-line justification: purpose-built retrieval embeddings with first-class query/passage asymmetry via `input_type` (`"query"` vs `"document"`), current (Jan 2026) generation, and the cost is effectively zero at this corpus size.
- **Output dimensionality: 1024** (default). Also configurable to 256 / 512 / 2048 via `output_dimension`. → **pgvector column `vector(1024)`.** [Voyage/MongoDB models doc + Voyage embeddings doc]
- Asymmetry: `input_type` takes `None` (default), `"query"`, or `"document"`; setting query/document prepends task-specific instructions before vectorization — embed card descriptions as `document`, rewritten search queries as `query`. [Voyage embeddings doc]
- Cost: **$0.06 / 1M tokens**, with **200M free tokens per account**. Embedding ~18k cards (~14M tokens on the assumption above) fits entirely inside the free allowance → **≈ $0** for the initial index; per-query embedding is negligible. Batch API is 33% cheaper but free credits don't apply to batch. [Voyage pricing doc]
- Anthropic fit: Anthropic ships **no** first-party embedding model and points customers to Voyage AI, so Voyage is the Claude-aligned embedding choice here rather than an off-brand one.
- Fallbacks:
  - **OpenAI `text-embedding-3-large`** — 3072 dims (Matryoshka-shortenable), $0.13 / 1M. Note: the `text-embedding-3` family has **no** query/passage asymmetry (no input_type), so you lose that feature. Would need `vector(3072)` (or a reduced dim). [OpenAI pricing]
  - **Cohere `embed-v4.0`** — default 1536 dims (256/512/1024/1536), supports images too. Cohere's embed API historically exposes `input_type` (`search_query` / `search_document`) for asymmetry — see "Unverified" below. [Cohere embed doc]

**Model-size note within Voyage:** `voyage-4-lite` ($0.02) and `voyage-3.5` ($0.06) are also viable; all voyage-4-series vectors share an embedding space (index with one, query with another). `voyage-4` (standard) is the balanced quality/cost default. Given the corpus is tiny and cost is free-tier-covered, prefer the higher-quality `voyage-4` over `-lite`.

**Revised 2026-09-30:** embed documents with `voyage-4-large` ($0.12) and keep `voyage-4` for queries, using the shared embedding space. `EMBED_VERSION` in `app/search/embedding_cache.py` covers only the query-side cache, so it doesn't change while queries stay on `voyage-4`. Document vectors carry no model stamp: `run_embedding_pass` only embeds rows whose vector is null, so switching models after real ingest would leave old and new vectors mixed unless the vectors are cleared first. Switching before the first real embedding run avoids that.

---

## Where Anthropic fits (repo default = Claude)

- **Parse + rewrite:** Claude Haiku 4.5 is a clean fit (structured outputs, cheap) — used here as the named fallback. Choosing GPT-5-mini as primary is purely about OpenAI's constrained-decoding maturity + lower price, not a knock on Haiku.
- **Enrichment:** Claude Haiku 4.5 + Message Batches is the Anthropic path and is the fallback; the GPT-4.1-mini primary is chosen for explicit `temperature=0` determinism + marginally lower batch cost.
- **Embeddings:** Anthropic has no embedding model and officially recommends Voyage AI, so the Voyage pick *is* the Anthropic-aligned choice.

Net: the system can run Anthropic-only (Haiku 4.5 for both LLM roles + Voyage for embeddings) with a small quality/determinism/cost tradeoff, which is a reasonable portfolio talking point.

---

## Sources (primary)

- OpenAI API pricing — https://developers.openai.com/api/docs/pricing (GPT-5-mini $0.25/$2.00; GPT-5-nano $0.05/$0.40; GPT-4.1-mini $0.40/$1.60; GPT-4.1-nano $0.10/$0.40; GPT-4o-mini $0.15/$0.60; Batch = 50% off; text-embedding-3-small $0.02, -3-large $0.13)
- Voyage AI models (via MongoDB Docs) — https://www.mongodb.com/docs/voyageai/models/ (voyage-4 / -lite / -large: default 1024 dims, options 256/512/1024/2048, 32k context)
- Voyage AI embeddings doc — https://docs.voyageai.com/docs/embeddings (`input_type` = None/query/document; voyage-4 default 1024)
- Voyage AI pricing — https://docs.voyageai.com/docs/pricing (voyage-4 $0.06/1M, voyage-4-lite $0.02, voyage-4-large $0.12; 200M free tokens/account; Batch −33%, free credits excluded from batch)
- Cohere Embed doc — https://docs.cohere.com/docs/cohere-embed (embed-v4.0 default 1536 dims; english/multilingual-v3.0 1024)
- Anthropic models + pricing — `claude-api` skill (cached 2026-06-24): Claude Haiku 4.5 $1.00/$5.00 per 1M, 200K context; structured outputs via `output_config.format` + `strict:true`; Message Batches −50%.
- Anthropic models + pricing (revision) — `claude-api` skill (cached 2026-09-25): Claude Sonnet 5.5 (`claude-sonnet-5-5`) $2.00/$10.00 per 1M, 1M context; non-default sampling params return 400; `thinking: {type: "disabled"}` returns 400; forced `tool_choice` returns 400; server-side fallbacks rejected on the Batches API.

## Unverified / assumptions (flagged)

- **Per-card token counts** (~800 in / ~200 out) are my estimate, not measured — the ~$5–8 enrichment total scales linearly with the real prompt size. Re-estimate with a token count once the enrichment prompt exists.
- **GPT-5 reasoning models and `temperature=0`:** my claim that the GPT-5 family doesn't treat temperature=0 as a hard determinism guarantee is based on OpenAI's reasoning-model behavior generally; I did not pin it to a specific primary doc line in this pass. It's the reason GPT-4.1-mini (non-reasoning) is the enrichment primary — verify against the reasoning-models guide if determinism is load-bearing.
- **Cohere `input_type` (search_query/search_document):** the fetched embed page did not enumerate the `input_type` values, so the asymmetry claim for the Cohere fallback rests on Cohere's known API rather than a line I captured here. Confirm on the Embed API reference before relying on it.
- **Anthropic pricing** comes from the `claude-api` skill's cached table (2026-06-24), not a live fetch of anthropic.com/pricing.
