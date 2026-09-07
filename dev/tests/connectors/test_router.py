import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.main import app
from app.rag.embeddings import get_embedding_provider
from app.rag.reranking import get_reranker
from tests.rag.fakes import FakeEmbeddingProvider, FakeReranker


@pytest.fixture(autouse=True)
def _override_dependencies(db_session: AsyncSession):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_embedding_provider] = FakeEmbeddingProvider
    # FakeReranker plutôt que le vrai cross-encoder : ce fichier appelle /rag/search (ligne ~48),
    # pas de poids ML à charger dans une suite de tests rapide (voir tests/rag/fakes.py).
    app.dependency_overrides[get_reranker] = FakeReranker
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


async def test_resyncing_the_same_connector_does_not_duplicate_documents(client: AsyncClient):
    await client.post("/connectors/mock/sync", json={})

    response = await client.post("/connectors/mock/sync", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["synced"] == 2
    assert body["errors"] == []

    search = await client.get("/rag/search", params={"q": "paiement", "top_k": 10})
    matches = [r for r in search.json()["results"] if "10 000 euros" in r["text"]]
    assert len(matches) == 1
