from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.registry import get_connector
from app.connectors.schemas import SyncResponse
from app.core.database import get_db
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.ingestion import ingest_document

router = APIRouter()


@router.post(
    "/{name}/sync",
    response_model=SyncResponse,
    summary="Synchroniser un connecteur vers la base de connaissances",
    description=(
        "Récupère les items du connecteur nommé, les convertit en documents et les envoie au "
        "pipeline d'ingestion RAG. `params` porte les arguments propres au connecteur "
        "(ex : `owner`/`repo` pour GitHub)."
    ),
)
async def sync_connector(
    name: str,
    params: dict[str, Any] = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> SyncResponse:
    connector = get_connector(name)
    items = await connector.fetch_items(**params)

    synced = 0
    errors: list[str] = []
    for item in items:
        try:
            document = connector.to_document(item)
            await ingest_document(
                db, source=document.source, content=document.content, provider=provider
            )
            synced += 1
        except Exception as exc:  # un item invalide ne doit pas interrompre la synchronisation
            errors.append(str(exc))

    return SyncResponse(connector=name, synced=synced, errors=errors)
