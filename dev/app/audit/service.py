from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog


async def write_log(
    db: AsyncSession,
    event_type: str,
    payload: dict,
    *,
    source: str,
    result: str | None = None,
) -> None:
    """Point de passage obligé pour tracer un événement (US-502) : `agent` et `gating` ne
    doivent jamais écrire directement dans `audit_logs`, seulement appeler cette fonction."""
    db.add(AuditLog(event_type=event_type, source=source, payload=payload, result=result))
    await db.commit()
