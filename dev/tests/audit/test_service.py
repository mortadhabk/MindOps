import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.audit.service import write_log


def _unique_event_type(label: str) -> str:
    # write_log fait son propre commit (voir docstring) : les lignes écrites via de vrais appels
    # API restent en base au-delà de la transaction du test. Un type d'événement unique évite
    # toute ambiguïté avec des lignes préexistantes plutôt que de supposer la table vide.
    return f"test.{label}.{uuid.uuid4().hex}"


async def test_write_log_persists_event(db_session: AsyncSession):
    event_type = _unique_event_type("persists")
    await write_log(
        db_session,
        event_type,
        {"proposal_id": 1, "decision": "approve"},
        source="gating",
    )

    logged = (
        await db_session.execute(select(AuditLog).where(AuditLog.event_type == event_type))
    ).scalar_one()
    assert logged.source == "gating"
    assert logged.payload == {"proposal_id": 1, "decision": "approve"}
    assert logged.result is None


async def test_write_log_stores_optional_result(db_session: AsyncSession):
    event_type = _unique_event_type("with-result")
    await write_log(
        db_session,
        event_type,
        {"proposal_id": 2},
        source="agent",
        result="livré: x",
    )

    logged = (
        await db_session.execute(select(AuditLog).where(AuditLog.event_type == event_type))
    ).scalar_one()
    assert logged.result == "livré: x"
