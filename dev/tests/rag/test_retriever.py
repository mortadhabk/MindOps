from app.rag.ingestion import ingest_document
from app.rag.retriever import search
from tests.rag.fakes import FakeEmbeddingProvider


async def test_search_returns_exact_match_first(db_session):
    provider = FakeEmbeddingProvider()
    await ingest_document(
        db_session, source="a", content="Le service de paiement echoue", provider=provider
    )
    await ingest_document(
        db_session, source="b", content="Le café est excellent ce matin", provider=provider
    )

    results = await search(
        db_session,
        "Le service de paiement echoue",
        provider,
        top_k=5,
        similarity_threshold=0.0,
    )

    assert results
    best_chunk, best_score = results[0]
    assert best_chunk.text == "Le service de paiement echoue"
    assert best_score > 0.99


async def test_search_respects_top_k(db_session):
    provider = FakeEmbeddingProvider()
    for i in range(5):
        await ingest_document(
            db_session,
            source=f"doc-{i}",
            content=f"Contenu numero {i} pour le test de pagination",
            provider=provider,
        )

    results = await search(
        db_session,
        "Contenu numero 2 pour le test de pagination",
        provider,
        top_k=2,
        similarity_threshold=0.0,
    )

    assert len(results) == 2


async def test_search_falls_back_to_exact_ticket_key_match(db_session):
    provider = FakeEmbeddingProvider()
    await ingest_document(
        db_session,
        source="jira:https://example.atlassian.net/browse/PROJ-42",
        content="Erreur de synchronisation du flux de paiement",
        provider=provider,
    )
    await ingest_document(
        db_session, source="other", content="Un contenu totalement different", provider=provider
    )

    # Seuil impossible à atteindre (max théorique = 1.0) : la recherche sémantique seule ne
    # renverrait jamais rien ici, isolant le comportement de repli par identifiant exact.
    results = await search(
        db_session,
        "Quel est le problème du ticket PROJ-42 ?",
        provider,
        top_k=1,
        similarity_threshold=1.1,
    )

    assert len(results) == 1
    chunk, score = results[0]
    assert score == 1.0
    assert "PROJ-42" in chunk.document.source


async def test_search_exact_ticket_key_match_is_case_insensitive(db_session):
    provider = FakeEmbeddingProvider()
    await ingest_document(
        db_session,
        source="jira:https://example.atlassian.net/browse/PROJ-42",
        content="Erreur de synchronisation",
        provider=provider,
    )

    results = await search(
        db_session, "probleme sur proj-42", provider, top_k=1, similarity_threshold=1.1
    )

    assert len(results) == 1


async def test_search_without_ticket_key_does_not_add_exact_matches(db_session):
    provider = FakeEmbeddingProvider()
    await ingest_document(
        db_session,
        source="jira:https://example.atlassian.net/browse/PROJ-42",
        content="Erreur de synchronisation",
        provider=provider,
    )

    results = await search(
        db_session, "une question sans identifiant", provider, top_k=1, similarity_threshold=1.1
    )

    assert results == []


async def test_search_filters_out_results_below_threshold(db_session):
    provider = FakeEmbeddingProvider()
    await ingest_document(
        db_session, source="a", content="Le service de paiement echoue", provider=provider
    )
    await ingest_document(
        db_session,
        source="b",
        content="Un texte totalement different et sans rapport",
        provider=provider,
    )

    results = await search(
        db_session,
        "Le service de paiement echoue",
        provider,
        top_k=5,
        similarity_threshold=0.9,
    )

    assert len(results) == 1
    assert results[0][0].text == "Le service de paiement echoue"
