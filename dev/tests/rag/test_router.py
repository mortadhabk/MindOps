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


async def test_ingest_then_search_end_to_end(client: AsyncClient):
    ingest_response = await client.post(
        "/rag/ingest",
        json={"source": "test-suite", "content": "Le service de paiement echoue en production"},
    )

    assert ingest_response.status_code == 200
    body = ingest_response.json()
    assert body["status"] == "complete"
    assert body["chunks_created"] == 1

    search_response = await client.get(
        "/rag/search",
        params={"q": "Le service de paiement echoue en production", "top_k": 3},
    )

    assert search_response.status_code == 200
    results = search_response.json()["results"]
    assert len(results) == 1
    assert results[0]["text"] == "Le service de paiement echoue en production"
    assert results[0]["score"] > 0.99


async def test_ingest_rejects_empty_content(client: AsyncClient):
    response = await client.post("/rag/ingest", json={"source": "test-suite", "content": ""})

    assert response.status_code == 422
