from app.rag.settings import _get_read_only, get_effective_rag_settings
from app.settings import store


def test_get_effective_rag_settings_uses_env_defaults_when_no_override():
    settings = get_effective_rag_settings()

    assert settings.rag_chunk_max_tokens > 0


def test_get_effective_rag_settings_uses_override_when_present():
    store._overrides["rag"] = {
        "rag_chunk_max_tokens": 50,
        "rag_chunk_overlap": 5,
        "rag_similarity_threshold": 0.9,
    }

    settings = get_effective_rag_settings()

    assert settings.rag_chunk_max_tokens == 50
    assert settings.rag_chunk_overlap == 5
    assert settings.rag_similarity_threshold == 0.9


def test_read_only_exposes_embedding_info_without_being_editable():
    info = _get_read_only()

    assert "embedding_provider" in info
    assert "embedding_model" in info


async def test_ingest_document_respects_the_rag_settings_override(db_session):
    from app.rag.ingestion import ingest_document
    from tests.rag.fakes import FakeEmbeddingProvider

    store._overrides["rag"] = {
        "rag_chunk_max_tokens": 2,
        "rag_chunk_overlap": 0,
        "rag_similarity_threshold": 0.2,
    }

    _document, chunks_created = await ingest_document(
        db_session,
        source="settings-override-test",
        content="un deux trois quatre cinq six",
        provider=FakeEmbeddingProvider(),
    )

    assert chunks_created == 3  # 6 mots / rag_chunk_max_tokens=2 -> 3 chunks
