import pytest
from sqlalchemy import select

from app.rag.embeddings.base import EmbeddingProvider
from app.rag.ingestion import chunk_text, ingest_document
from app.rag.models import Chunk
from tests.rag.fakes import FakeEmbeddingProvider


class _FailingEmbeddingProvider(EmbeddingProvider):
    dimension = 384

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("simulated embedding failure")


def test_chunk_text_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_shorter_than_max_returns_single_chunk():
    text = "quelques mots seulement"
    assert chunk_text(text, max_tokens=50, overlap=5) == [text]


def test_chunk_text_overlap_between_consecutive_chunks():
    words = [f"mot{i}" for i in range(45)]
    text = " ".join(words)

    chunks = chunk_text(text, max_tokens=20, overlap=5)

    assert len(chunks) == 3
    for current, following in zip(chunks, chunks[1:], strict=False):
        assert current.split()[-5:] == following.split()[:5]


def test_chunk_text_rejects_overlap_greater_or_equal_to_max_tokens():
    with pytest.raises(ValueError):
        chunk_text("peu importe", max_tokens=10, overlap=10)


def test_chunk_text_rejects_non_positive_max_tokens():
    with pytest.raises(ValueError):
        chunk_text("peu importe", max_tokens=0)


async def test_ingest_document_creates_chunks_with_embeddings(db_session):
    document, chunks_created = await ingest_document(
        db_session,
        source="test-suite",
        content="Le service de paiement echoue en production depuis ce matin",
        provider=FakeEmbeddingProvider(),
    )

    assert document.status == "complete"
    assert chunks_created == 1

    stored = await db_session.execute(select(Chunk).where(Chunk.document_id == document.id))
    stored_chunks = stored.scalars().all()
    assert len(stored_chunks) == 1
    assert len(stored_chunks[0].embedding) == FakeEmbeddingProvider.dimension


async def test_ingest_document_marks_partial_on_embedding_failure(db_session):
    document, chunks_created = await ingest_document(
        db_session,
        source="test-suite",
        content="Un contenu qui echouera a l'embedding",
        provider=_FailingEmbeddingProvider(),
    )

    assert document.status == "partial"
    assert chunks_created == 0

    stored = await db_session.execute(select(Chunk).where(Chunk.document_id == document.id))
    assert stored.scalars().all() == []
