from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.main import app
from app.settings import store as settings_store


@pytest.fixture(autouse=True)
def _reset_settings_overrides_cache():
    """`settings_store._overrides` est un cache mémoire global (Epic 9, voir sa docstring) — pas
    une transaction DB, donc jamais annulé par le rollback de `db_session`. Sans ce nettoyage, un
    override posé par un test resterait visible par tous les tests suivants du même run."""
    settings_store._overrides.clear()
    yield
    settings_store._overrides.clear()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.connect() as connection:
        await connection.begin()
        # join_transaction_mode="create_savepoint" : un session.commit() fait par le
        # code teste ne cloture qu'un SAVEPOINT, jamais la transaction externe ci-dessous
        # -> connection.rollback() annule tout, meme si le code a appele commit().
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await connection.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
