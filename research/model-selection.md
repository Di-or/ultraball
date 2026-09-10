# Hosted model selection: parse, enrichment, embeddings

**Ticket:** [#3 — Choose hosted models for parse, enrichment, and embeddings](https://github.com/Di-or/ultraball/issues/3)
**Date:** 2026-08-28
**Scope:** Hosted API models (not local) for a Pokémon TCG deckbuilder's conceptual-search system: ~18,000 cards embedded into Postgres + pgvector.

All prices verified against provider primary sources (pricing/docs pages) as cited. Anything I could not tie to a primary source is called out under **Unverified / assumptions** at the end.

---

## TL;DR — the three picks

| Role | Recommendation | Rough cost | Fallback |
|---|---|---|---|
| 1. Parse + rewrite (per query) | **OpenAI GPT-5-mini** (Structured Outputs, strict JSON schema) | $0.25 in / $2.00 out per 1M tok | Claude Haiku 4.5 |
| 2. Enrichment (one-time batch, ~18k cards) | **OpenAI GPT-4.1-mini** via Batch API, `temperature=0` | $0.20 in / $0.80 out per 1M tok (batch); **~$5–8 total** for 18k cards | Claude Haiku 4.5 (Batch) / GPT-5-nano (Batch) |
| 3. Embedding | **Voyage `voyage-4`**, `input_type` query/document | $0.06 per 1M tok; ~18k cards fits inside the 200M free tokens (≈ $0) | OpenAI `text-embedding-3-large` / Cohere `embed-v4.0` |

**Embedding vector dimensionality: 1024** (Voyage `voyage-4` default) → pgvector column `vector(1024)`.

---

## Role 1 — Parse + rewrite model

**Requirement:** small/cheap, must support structured output / constrained decoding (JSON schema). Splits a natural-language query into structured filters + a rewritten "concept" phrase. One call per user query; latency + cost matter but it's tiny and cacheable.

**Pick: OpenAI GPT-5-mini.**
- One-line justification: OpenAI Structured Outputs does true constrained decoding against a strict JSON schema (guaranteed-valid JSON, not best-effort), and GPT-5-mini has the instruction-following to produce a good rewritten "concept" phrase while staying cheap.
- Cost: **$0.25 / 1M input, $2.00 / 1M output** (standard). Prompt-cached input reads are cheaper, which matters here since the parse system prompt/schema is a stable prefix. [OpenAI pricing]
- Fallback: **Claude Haiku 4.5** — $1.00 / 1M in, $5.00 / 1M out; supports structured outputs via `output_config: {format: {...}}` with `strict: true`. This is the natural Anthropic-aligned choice for the repo's Claude default. [claude-api skill, cached 2026-06-24]

**Cheaper alternative if rewrite quality holds:** GPT-5-nano ($0.05 in / $0.40 out) or GPT-4.1-nano ($0.10 / $0.40) — both support Structured Outputs. Worth an eval; the "concept" rewrite is the part that benefits from the larger mini model.

## Role 2 — Enrichment model

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

## Unverified / assumptions (flagged)

- **Per-card token counts** (~800 in / ~200 out) are my estimate, not measured — the ~$5–8 enrichment total scales linearly with the real prompt size. Re-estimate with a token count once the enrichment prompt exists.
- **GPT-5 reasoning models and `temperature=0`:** my claim that the GPT-5 family doesn't treat temperature=0 as a hard determinism guarantee is based on OpenAI's reasoning-model behavior generally; I did not pin it to a specific primary doc line in this pass. It's the reason GPT-4.1-mini (non-reasoning) is the enrichment primary — verify against the reasoning-models guide if determinism is load-bearing.
- **Cohere `input_type` (search_query/search_document):** the fetched embed page did not enumerate the `input_type` values, so the asymmetry claim for the Cohere fallback rests on Cohere's known API rather than a line I captured here. Confirm on the Embed API reference before relying on it.
- **Anthropic pricing** comes from the `claude-api` skill's cached table (2026-06-24), not a live fetch of anthropic.com/pricing.
