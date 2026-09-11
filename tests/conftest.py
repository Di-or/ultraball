from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.community.postgres import PostgresContainer

from app.catalog.models import Base as CatalogBase
from app.config import Settings
from app.enrichment.models import Base as EnrichmentBase
from app.main import create_app

_ALL_TABLE_NAMES = [table.name for table in (*CatalogBase.metadata.sorted_tables, *EnrichmentBase.metadata.sorted_tables)]


@pytest.fixture(scope="session")
def postgres_container() -> AsyncIterator[PostgresContainer]:
    with PostgresContainer("pgvector/pgvector:pg16", driver="asyncpg") as container:
        yield container


@pytest_asyncio.fixture
async def client(postgres_container: PostgresContainer) -> AsyncIterator[AsyncClient]:
    settings = Settings(database_url=postgres_container.get_connection_url())
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest_asyncio.fixture
async def db_session(postgres_container: PostgresContainer) -> AsyncIterator[AsyncSession]:
    """A session against a real Postgres, with the app's tables already created."""
    settings = Settings(database_url=postgres_container.get_connection_url())
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        async with app.state.session_factory() as session:
            # The Postgres container is session-scoped, so rows from earlier tests
            # would otherwise leak in; start every test from an empty database.
            await session.execute(text(f"TRUNCATE TABLE {', '.join(_ALL_TABLE_NAMES)} RESTART IDENTITY CASCADE"))
            await session.commit()
            yield session
