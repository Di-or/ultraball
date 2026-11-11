# Ultraball

A conceptual-search Pokémon TCG deckbuilder. See `pokemon-deckbuilder-context-upd.md` for the project concept and architecture, and GitHub Issues for specs and tickets.

## Running locally

```
docker compose up
```

FastAPI serves on `http://localhost:8000`; `GET /health` returns `{"status": "ok"}` once the app can reach Postgres.

## Seeding dummy data

The real TCGdex ingest isn't built yet, so a fresh database is empty. With `docker compose up` running, load a few made-up sets, cards, enrichments and embeddings:

```
uv run python -m scripts.seed_dummy
```

It connects to Postgres on `localhost:5432` (the port `docker compose` publishes) unless `DATABASE_URL` says otherwise. Safe to run more than once, but it refuses to run if the database already holds real (non-dummy) sets. To go back to real data only, reset the volume with `docker compose down -v`. Search results from the fake data aren't meaningful.

## Building the catalog

The runner builds the real catalog from TCGdex: it ingests every **Included set** (`app/catalog/included_sets.py`) and prints the Catalog override report, then submits tagging batches for new, changed, failed and `needs_repair` card entities, waits for them and applies them, and finally embeds every card that has a description but no vector. It prints a summary of each step as it goes.

```
uv run python -m scripts.build_catalog
```

It writes to `DATABASE_URL` (the local Postgres by default) and spends real money: it needs `ANTHROPIC_API_KEY` (or `CLAUDE_API_KEY`) with Console credits and `VOYAGE_API_KEY`. The full catalog costs about $4.50. Run it in its own terminal, not inside an agent session. The tagging batch usually takes minutes to an hour, but can take up to 24h.

Every step is idempotent, so re-running is safe: it only tags cards whose text is new or changed (plus failed and `needs_repair` ones), only embeds cards without a current vector, and after a crash it picks up a batch still in flight. To add a set, add its id to `INCLUDED_SETS` and run it again.

To run on just some printings (the 72-card trial), pass their printing ids. The run is then limited to those printings' sets, and tagging and embedding to their card entities:

```
uv run python -m scripts.build_catalog --printings sv06.5-047 sv01-196
uv run python -m scripts.build_catalog --printings-file printings.txt   # whitespace-separated ids
```

**After a version bump, concept search has a gap until the run finishes.** Submitting a tagging batch clears each re-tagged card's vector, and semantic search ranks only `completed` rows with a vector under the current `(TAXONOMY_VERSION, PROMPT_VERSION)` stamp. So after a bump, concept search returns nothing for re-tagged cards until the runner finishes: semantic-only queries come back empty, mixed queries rank by tags only, and plain filtering and browsing are unaffected. Most of that time is the tagging batch. Deploy order doesn't avoid it, because the app and the runner read the same version constants. The routine is: **bump the version, then run the runner straight away.** The runner prints this reminder whenever it submits a batch.

## Development

```
uv sync
uv run pytest
```

Tests drive the app through the FastAPI test client against a real, containerized Postgres+pgvector instance (via `testcontainers`) — no hosted model provider calls. `ParseClient` and `EmbeddingClient` (`app/clients/`) are the seams hosted models plug into; tests use the canned stubs in `tests/stubs.py`.

## Frontend

```
cd frontend
npm install
npm run dev
```

Vite serves on `http://localhost:5173` and proxies `/search`, `/cards`, `/decks`, `/energy` to the FastAPI backend on `:8000` (`docker compose up` in another terminal). `npm run typecheck` and `npm test` (Vitest) run the frontend's own checks.
