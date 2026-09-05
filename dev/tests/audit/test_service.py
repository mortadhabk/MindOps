from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.audit.service import write_log


async def test_write_log_persists_event(db_session: AsyncSession):
    await write_log(
        db_session,
        "gating.decision",
        {"proposal_id": 1, "decision": "approve"},
        source="gating",
    )

    logged = (await db_session.execute(select(AuditLog))).scalar_one()
    assert logged.event_type == "gating.decision"
    assert logged.source == "gating"
    assert logged.payload == {"proposal_id": 1, "decision": "approve"}
    assert logged.result is None


async def test_write_log_stores_optional_result(db_session: AsyncSession):
    await write_log(
        db_session,
        "agent.action_proposed",
        {"proposal_id": 2},
        source="agent",
        result="livré: x",
    )

    logged = (await db_session.execute(select(AuditLog))).scalar_one()
    assert logged.result == "livré: x"
