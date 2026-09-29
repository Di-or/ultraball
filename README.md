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

It connects to Postgres on `localhost:5432` (the port `docker compose` publishes) unless `DATABASE_URL` says otherwise. Safe to run more than once. Search results from the fake data aren't meaningful.

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
