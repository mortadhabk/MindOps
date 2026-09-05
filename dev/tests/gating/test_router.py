import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.gating import queue_service
from app.gating.models import ActionStatus
from app.gating.router import get_graph_resumer
from app.main import app


@pytest.fixture(autouse=True)
def _override_dependencies(db_session: AsyncSession):
    async def _get_db():
        yield db_session

    resumed_ids: list[int] = []

    async def _fake_resumer(proposal_id: int) -> None:
        resumed_ids.append(proposal_id)

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_graph_resumer] = lambda: _fake_resumer
    app.state.resumed_ids = resumed_ids
    yield
    app.dependency_overrides.clear()


async def test_pending_lists_only_pending_proposals(client: AsyncClient, db_session: AsyncSession):
    await queue_service.create_proposal(
        db_session,
        tool_call_id="call-1",
        conversation_id="conv-1",
        action_type="send_email",
        parameters={"to": "client@example.com"},
        status=ActionStatus.PENDING,
    )
    await queue_service.create_proposal(
        db_session,
        tool_call_id="call-2",
        conversation_id="conv-1",
        action_type="send_email",
        parameters={},
        status=ActionStatus.APPROVED,
    )

    response = await client.get("/gating/pending")

    assert response.status_code == 200
    body = response.json()
    assert [item["action_type"] for item in body] == ["send_email"]
    assert body[0]["status"] == "pending"


async def test_decide_approve_updates_status_and_triggers_resume(
    client: AsyncClient, db_session: AsyncSession
):
    proposal = await queue_service.create_proposal(
        db_session,
        tool_call_id="call-1",
        conversation_id="conv-1",
        action_type="send_email",
        parameters={"to": "client@example.com"},
        status=ActionStatus.PENDING,
    )

    response = await client.post(f"/gating/{proposal.id}/decide", json={"decision": "approve"})

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert app.state.resumed_ids == [proposal.id]


async def test_decide_reject_also_triggers_resume(client: AsyncClient, db_session: AsyncSession):
    proposal = await queue_service.create_proposal(
        db_session,
        tool_call_id="call-1",
        conversation_id="conv-1",
        action_type="send_email",
        parameters={},
        status=ActionStatus.PENDING,
    )

    response = await client.post(f"/gating/{proposal.id}/decide", json={"decision": "reject"})

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    # Le graphe doit reprendre même en cas de rejet : c'est ce qui débloque interrupt() pour
    # que l'agent puisse répondre à l'utilisateur (voir orchestrator._run_sensitive_tool).
    assert app.state.resumed_ids == [proposal.id]


async def test_decide_unknown_proposal_returns_404(client: AsyncClient):
    response = await client.post("/gating/999999/decide", json={"decision": "approve"})
    assert response.status_code == 404


async def test_decide_rejects_invalid_decision_value(client: AsyncClient, db_session: AsyncSession):
    proposal = await queue_service.create_proposal(
        db_session,
        tool_call_id="call-1",
        conversation_id="conv-1",
        action_type="send_email",
        parameters={},
        status=ActionStatus.PENDING,
    )

    response = await client.post(f"/gating/{proposal.id}/decide", json={"decision": "maybe"})

    assert response.status_code == 422
