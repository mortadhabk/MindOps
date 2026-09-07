from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.ingestion import ingest_document
from app.rag.reranking import Reranker, get_reranker
from app.rag.retriever import search as search_chunks
from app.rag.schemas import DocumentIn, IngestResponse, SearchResponse, SearchResultItem

router = APIRouter()


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Ingérer un document",
    description=(
        "Découpe le contenu en fragments (chunks), calcule leurs embeddings et les stocke. "
        "Renvoie `status: partial` si le calcul d'embedding échoue, sans perdre le document."
    ),
)
async def ingest(
    payload: DocumentIn,
    db: AsyncSession = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> IngestResponse:
    document, chunks_created = await ingest_document(
        db, source=payload.source, content=payload.content, provider=provider
    )
    return IngestResponse(
        document_id=document.id, status=document.status, chunks_created=chunks_created
    )


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Rechercher les fragments les plus pertinents",
    description=(
        "Calcule l'embedding de la question, présélectionne les fragments les plus proches par "
        "similarité cosinus (filtrés par le seuil `RAG_SIMILARITY_THRESHOLD`), puis les "
        "réordonne avec un cross-encoder si le reranking est activé avant de renvoyer les "
        "`top_k` premiers. Le score renvoyé reste la similarité cosinus d'origine."
    ),
)
async def search_endpoint(
    q: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
    reranker: Reranker = Depends(get_reranker),
) -> SearchResponse:
    results = await search_chunks(db, q, provider, top_k=top_k, reranker=reranker)
    return SearchResponse(
        query=q,
        results=[
            SearchResultItem(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_source=chunk.document.source,
                connector_instance_id=chunk.document.connector_instance_id,
                text=chunk.text,
                score=score,
            )
            for chunk, score in results
        ],
    )
