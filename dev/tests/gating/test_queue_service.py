import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ActionNotFoundError
from app.gating import queue_service
from app.gating.models import ActionStatus


async def _make_pending(db_session: AsyncSession, tool_call_id: str = "call-1"):
    return await queue_service.create_proposal(
        db_session,
        tool_call_id=tool_call_id,
        conversation_id="conv-1",
        action_type="send_email",
        parameters={"to": "client@example.com"},
        status=ActionStatus.PENDING,
    )


async def test_create_proposal_then_found_by_tool_call_id(db_session: AsyncSession):
    created = await _make_pending(db_session)

    found = await queue_service.get_proposal_for_tool_call(db_session, "call-1")

    assert found is not None
    assert found.id == created.id
    assert found.status == ActionStatus.PENDING


async def test_get_proposal_for_tool_call_returns_none_when_absent(db_session: AsyncSession):
    found = await queue_service.get_proposal_for_tool_call(db_session, "unknown-call")
    assert found is None


async def test_list_pending_only_returns_pending_proposals(db_session: AsyncSession):
    pending = await _make_pending(db_session, tool_call_id="call-pending")
    approved = await queue_service.create_proposal(
        db_session,
        tool_call_id="call-approved",
        conversation_id="conv-1",
        action_type="send_email",
        parameters={},
        status=ActionStatus.APPROVED,
    )

    result = await queue_service.list_pending(db_session)

    ids = {proposal.id for proposal in result}
    assert pending.id in ids
    assert approved.id not in ids


async def test_decide_approve_updates_status_and_decided_at(db_session: AsyncSession):
    proposal = await _make_pending(db_session)

    decided = await queue_service.decide(db_session, proposal.id, "approve")

    assert decided.status == ActionStatus.APPROVED
    assert decided.decided_at is not None


async def test_decide_reject_updates_status(db_session: AsyncSession):
    proposal = await _make_pending(db_session)

    decided = await queue_service.decide(db_session, proposal.id, "reject")

    assert decided.status == ActionStatus.REJECTED


async def test_decide_twice_raises_action_not_found(db_session: AsyncSession):
    proposal = await _make_pending(db_session)
    await queue_service.decide(db_session, proposal.id, "approve")

    with pytest.raises(ActionNotFoundError):
        await queue_service.decide(db_session, proposal.id, "approve")


async def test_decide_unknown_proposal_raises_action_not_found(db_session: AsyncSession):
    with pytest.raises(ActionNotFoundError):
        await queue_service.decide(db_session, 999_999, "approve")
