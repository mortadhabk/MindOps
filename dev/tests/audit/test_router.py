import uuid

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


def _unique_event_type(label: str) -> str:
    # write_log commite réellement (voir tests/audit/test_service.py) : la base de dev partagée
    # peut déjà contenir des lignes d'exécutions précédentes. Un type d'événement unique par test
    # permet d'isoler nos propres lignes sans supposer la table vide.
    return f"test.{label}.{uuid.uuid4().hex}"


async def test_logs_lists_events_most_recent_first(client: AsyncClient, db_session: AsyncSession):
    tag = uuid.uuid4().hex
    first, second = f"test.first.{tag}", f"test.second.{tag}"
    await write_log(db_session, first, {"conversation_id": "conv-1"}, source="agent")
    await write_log(db_session, second, {"proposal_id": 1, "decision": "approve"}, source="gating")

    response = await client.get("/audit/logs")

    assert response.status_code == 200
    own_event_types = [item["event_type"] for item in response.json() if tag in item["event_type"]]
    assert own_event_types == [second, first]


async def test_logs_filters_by_event_type(client: AsyncClient, db_session: AsyncSession):
    event_type = _unique_event_type("filtered")
    await write_log(db_session, event_type, {"conversation_id": "conv-1"}, source="agent")
    await write_log(db_session, _unique_event_type("other"), {"proposal_id": 1}, source="gating")

    response = await client.get("/audit/logs", params={"event_type": event_type})

    assert response.status_code == 200
    assert [item["event_type"] for item in response.json()] == [event_type]
