from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.audit.schemas import AuditLogOut
from app.core.database import get_db

router = APIRouter()


@router.get(
    "/logs",
    response_model=list[AuditLogOut],
    summary="Consulter le journal d'audit",
    description=(
        "Liste les événements tracés (appels LLM, propositions d'action, décisions de "
        "validation), du plus récent au plus ancien, avec filtres optionnels par type "
        "d'événement et par date (US-503)."
    ),
)
async def logs(
    event_type: str | None = Query(default=None, examples=["gating.decision"]),
    since: datetime | None = Query(
        default=None, description="Ne renvoyer que les événements créés à partir de cette date"
    ),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogOut]:
    # id en second critère : plusieurs événements peuvent partager le même created_at (résolution
    # de la seconde, ou même transaction Postgres) sans que leur ordre d'écriture ne soit perdu.
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if event_type is not None:
        stmt = stmt.where(AuditLog.event_type == event_type)
    if since is not None:
        stmt = stmt.where(AuditLog.created_at >= since)
    result = await db.execute(stmt)
    return [AuditLogOut.model_validate(log) for log in result.scalars()]
