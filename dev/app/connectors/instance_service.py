from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.models import ConnectorInstance
from app.connectors.registry import get_connector
from app.core.exceptions import ConnectorConfigError, ConnectorInstanceNotFoundError
from app.rag.embeddings import EmbeddingProvider
from app.rag.ingestion import ingest_document


async def list_instances(db: AsyncSession) -> list[ConnectorInstance]:
    result = await db.execute(select(ConnectorInstance).order_by(ConnectorInstance.id))
    return list(result.scalars())


async def create_instance(
    db: AsyncSession,
    *,
    connector_type: str,
    display_name: str,
    config: dict,
    position_x: float = 0,
    position_y: float = 0,
) -> ConnectorInstance:
    connector = get_connector(connector_type)  # lève ConnectorNotFoundError si type inconnu
    # Valide la config contre le schéma du connecteur avant écriture, plutôt que de découvrir un
    # paramètre manquant/mal typé seulement au moment de la synchronisation.
    try:
        validated_config = connector.config_schema.model_validate(config).model_dump()
    except ValidationError as exc:
        raise ConnectorConfigError(
            f"Configuration invalide pour le connecteur « {connector_type} »",
            details={"errors": exc.errors(include_url=False, include_context=False)},
        ) from exc

    instance = ConnectorInstance(
        connector_type=connector_type,
        display_name=display_name,
        config=validated_config,
        position_x=position_x,
        position_y=position_y,
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    return instance


async def _get_or_raise(db: AsyncSession, instance_id: int) -> ConnectorInstance:
    instance = await db.get(ConnectorInstance, instance_id)
    if instance is None:
        raise ConnectorInstanceNotFoundError(f"Instance de connecteur {instance_id} introuvable.")
    return instance


async def update_position(
    db: AsyncSession, instance_id: int, *, position_x: float, position_y: float
) -> ConnectorInstance:
    instance = await _get_or_raise(db, instance_id)
    instance.position_x = position_x
    instance.position_y = position_y
    await db.commit()
    await db.refresh(instance)
    return instance


async def delete_instance(db: AsyncSession, instance_id: int) -> None:
    instance = await _get_or_raise(db, instance_id)
    await db.delete(instance)
    await db.commit()


async def mark_syncing(db: AsyncSession, instance_id: int) -> ConnectorInstance:
    instance = await _get_or_raise(db, instance_id)
    instance.status = "syncing"
    await db.commit()
    await db.refresh(instance)
    return instance


async def run_sync(db: AsyncSession, instance_id: int, provider: EmbeddingProvider) -> None:
    """Synchronise réellement une instance et met à jour son statut. Prend `db` en paramètre
    plutôt que d'ouvrir sa propre session : c'est à l'appelant (voir `connectors.router`, qui
    l'exécute en tâche de fond après la réponse HTTP) de fournir une session encore valide."""
    instance = await db.get(ConnectorInstance, instance_id)
    if instance is None:
        return

    connector = get_connector(instance.connector_type)
    synced = 0
    errors: list[str] = []
    try:
        items = await connector.fetch_items(**instance.config)
        for item in items:
            try:
                document = connector.to_document(item)
                await ingest_document(
                    db,
                    source=document.source,
                    content=document.content,
                    provider=provider,
                    connector_instance_id=instance_id,
                )
                synced += 1
            except Exception as exc:  # un item invalide ne doit pas interrompre la sync
                errors.append(str(exc))
    except Exception as exc:  # ex: source injoignable, config invalide côté API externe
        errors.append(str(exc))

    instance.status = "error" if synced == 0 and errors else "success"
    instance.last_result = {"synced": synced, "errors": errors}
    # .replace(tzinfo=None) : colonne TIMESTAMP WITHOUT TIME ZONE, comme gating.ActionProposal
    instance.last_synced_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
