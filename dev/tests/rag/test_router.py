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
    # FakeReranker plutôt que le vrai cross-encoder : pas de poids ML à charger dans une suite de
    # tests rapide (voir tests/rag/fakes.py).
    app.dependency_overrides[get_reranker] = FakeReranker
    yield
    app.dependency_overrides.clear()


async def test_ingest_then_search_end_to_end(client: AsyncClient):
    from app.settings import store

    # La base de test partage la vraie base de dev (voir conftest.py, db_session) : avec le
    # reranker actif par défaut, le pool de candidats passe de `top_k` à RERANK_POOL_SIZE (20),
    # ce qui engloberait du vrai contenu déjà présent. Seuil relevé pour ne garder que le match
    # quasi exact, quelle que soit la taille du pool interrogé.
    store._overrides["rag"] = {"rag_similarity_threshold": 0.99}

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
