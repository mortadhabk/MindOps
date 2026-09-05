import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import write_log
from app.core.database import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _override_db(db_session: AsyncSession):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()


async def test_logs_lists_events_most_recent_first(client: AsyncClient, db_session: AsyncSession):
    await write_log(db_session, "agent.llm_call", {"conversation_id": "conv-1"}, source="agent")
    await write_log(
        db_session, "gating.decision", {"proposal_id": 1, "decision": "approve"}, source="gating"
    )

    response = await client.get("/audit/logs")

    assert response.status_code == 200
    body = response.json()
    assert [item["event_type"] for item in body] == ["gating.decision", "agent.llm_call"]


async def test_logs_filters_by_event_type(client: AsyncClient, db_session: AsyncSession):
    await write_log(db_session, "agent.llm_call", {"conversation_id": "conv-1"}, source="agent")
    await write_log(
        db_session, "gating.decision", {"proposal_id": 1, "decision": "approve"}, source="gating"
    )

    response = await client.get("/audit/logs", params={"event_type": "gating.decision"})

    assert response.status_code == 200
    body = response.json()
    assert [item["event_type"] for item in body] == ["gating.decision"]
