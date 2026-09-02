import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.main import app
from app.rag.embeddings import get_embedding_provider
from tests.rag.fakes import FakeEmbeddingProvider


@pytest.fixture(autouse=True)
def _override_dependencies(db_session: AsyncSession):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_embedding_provider] = FakeEmbeddingProvider
    yield
    app.dependency_overrides.clear()


async def test_sync_mock_connector_ingests_fixed_items(client: AsyncClient):
    response = await client.post("/connectors/mock/sync", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["connector"] == "mock"
    assert body["synced"] == 2
    assert body["errors"] == []


async def test_sync_unknown_connector_returns_404(client: AsyncClient):
    response = await client.post("/connectors/does-not-exist/sync", json={})

    assert response.status_code == 404
