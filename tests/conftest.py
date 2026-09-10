from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.community.postgres import PostgresContainer

from app.config import Settings
from app.main import create_app


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
            yield session
