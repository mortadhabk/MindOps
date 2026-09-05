from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors import instance_service
from app.connectors.registry import get_connector, list_connector_types
from app.connectors.schemas import (
    ConnectorInstanceCreate,
    ConnectorInstanceOut,
    ConnectorInstancePositionUpdate,
    ConnectorTypeOut,
    SyncResponse,
)
from app.core.database import async_session_factory, get_db
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.ingestion import ingest_document

router = APIRouter()

SyncRunner = Callable[[int, EmbeddingProvider], Awaitable[None]]


async def _default_sync_runner(instance_id: int, provider: EmbeddingProvider) -> None:
    """Implémentation par défaut, exécutée en tâche de fond (BackgroundTasks) : la session de la
    requête HTTP est déjà fermée quand ce code s'exécute (réponse déjà renvoyée au client), donc
    on ouvre une session dédiée — même raison que `agent.resume_service.resume_agent_graph`.
    Remplacée dans les tests par un enregistreur factice (voir tests/connectors), pour tester le
    déclenchement de la synchronisation sans dépendre de cette gymnastique de session."""
    async with async_session_factory() as db:
        await instance_service.run_sync(db, instance_id, provider)


def get_sync_runner() -> SyncRunner:
    return _default_sync_runner


@router.post(
    "/{name}/sync",
    response_model=SyncResponse,
    summary="Synchroniser un connecteur vers la base de connaissances",
    description=(
        "Récupère les items du connecteur nommé, les convertit en documents et les envoie au "
        "pipeline d'ingestion RAG. `params` porte les arguments propres au connecteur "
        "(ex : `owner`/`repo` pour GitHub). Synchrone et sans mémorisation de la configuration — "
        "voir `/connectors/instances` (Epic 8, Studio) pour une source configurée et pilotable "
        "graphiquement."
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


@router.get(
    "/types",
    response_model=list[ConnectorTypeOut],
    summary="Lister les types de connecteurs disponibles",
    description=(
        "Alimente la palette du Studio (Epic 8) : chaque type porte son schéma de configuration "
        "(JSON Schema de `Connector.config_schema`), utilisé pour générer le formulaire côté "
        "front sans dupliquer la définition des champs."
    ),
)
async def connector_types() -> list[ConnectorTypeOut]:
    return [
        ConnectorTypeOut(
            name=info.name,
            display_name=info.display_name,
            description=info.description,
            config_schema=info.config_schema,
        )
        for info in list_connector_types()
    ]


@router.get(
    "/instances",
    response_model=list[ConnectorInstanceOut],
    summary="Lister les instances de connecteur configurées",
    description="Redessine le canvas du Studio au chargement (Epic 8) : un nœud par instance.",
)
async def list_instances(db: AsyncSession = Depends(get_db)) -> list[ConnectorInstanceOut]:
    instances = await instance_service.list_instances(db)
    return [ConnectorInstanceOut.model_validate(instance) for instance in instances]


@router.post(
    "/instances",
    response_model=ConnectorInstanceOut,
    status_code=201,
    summary="Créer une instance de connecteur",
    description=(
        "Déposée depuis la palette du Studio (Epic 8) : `config` est validée contre le "
        "`config_schema` du type de connecteur avant écriture."
    ),
)
async def create_instance(
    payload: ConnectorInstanceCreate, db: AsyncSession = Depends(get_db)
) -> ConnectorInstanceOut:
    instance = await instance_service.create_instance(
        db,
        connector_type=payload.connector_type,
        display_name=payload.display_name,
        config=payload.config,
        position_x=payload.position_x,
        position_y=payload.position_y,
    )
    return ConnectorInstanceOut.model_validate(instance)


@router.patch(
    "/instances/{instance_id}",
    response_model=ConnectorInstanceOut,
    summary="Déplacer une instance de connecteur sur le canvas",
    description="Persiste la position du nœud (Epic 8) après un glisser-déposer sur le canvas.",
)
async def update_instance_position(
    instance_id: int,
    payload: ConnectorInstancePositionUpdate,
    db: AsyncSession = Depends(get_db),
) -> ConnectorInstanceOut:
    instance = await instance_service.update_position(
        db, instance_id, position_x=payload.position_x, position_y=payload.position_y
    )
    return ConnectorInstanceOut.model_validate(instance)


@router.delete(
    "/instances/{instance_id}",
    status_code=204,
    summary="Supprimer une instance de connecteur",
)
async def delete_instance(instance_id: int, db: AsyncSession = Depends(get_db)) -> None:
    await instance_service.delete_instance(db, instance_id)


@router.post(
    "/instances/{instance_id}/sync",
    response_model=ConnectorInstanceOut,
    summary="Déclencher la synchronisation d'une instance de connecteur",
    description=(
        "Marque l'instance en cours de synchronisation puis lance le travail réel en tâche de "
        "fond (Epic 8) : la réponse revient immédiatement avec `status: \"syncing\"`, le résultat "
        "se consulte via `GET /connectors/instances` (le Studio l'interroge par polling)."
    ),
)
async def sync_instance(
    instance_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
    sync_runner: SyncRunner = Depends(get_sync_runner),
) -> ConnectorInstanceOut:
    instance = await instance_service.mark_syncing(db, instance_id)
    background_tasks.add_task(sync_runner, instance_id, provider)
    return ConnectorInstanceOut.model_validate(instance)
