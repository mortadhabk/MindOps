from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import write_log
from app.core.exceptions import ActionNotFoundError
from app.gating.models import ActionProposal, ActionStatus


async def get_proposal_for_tool_call(db: AsyncSession, tool_call_id: str) -> ActionProposal | None:
    """Recherche une proposition déjà créée pour cet appel d'outil (protection anti-doublon,
    nécessaire car le nœud qui appelle interrupt() est rejoué depuis son début à la reprise)."""
    result = await db.execute(
        select(ActionProposal).where(ActionProposal.tool_call_id == tool_call_id)
    )
    return result.scalar_one_or_none()


async def create_proposal(
    db: AsyncSession,
    *,
    tool_call_id: str,
    conversation_id: str,
    action_type: str,
    parameters: dict,
    status: ActionStatus,
) -> ActionProposal:
    proposal = ActionProposal(
        tool_call_id=tool_call_id,
        conversation_id=conversation_id,
        action_type=action_type,
        parameters=parameters,
        status=status,
    )
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)
    return proposal


async def list_pending(db: AsyncSession) -> list[ActionProposal]:
    result = await db.execute(
        select(ActionProposal).where(ActionProposal.status == ActionStatus.PENDING)
    )
    return list(result.scalars())


async def decide(db: AsyncSession, proposal_id: int, decision: str) -> ActionProposal:
    """Approuve ou rejette une proposition en attente (US-403).

    L'exécution effective de l'action (US-405) n'a pas lieu ici : elle est déclenchée par
    l'appelant (`gating/router.py`) via la reprise du graphe LangGraph interrompu, pour que ce
    module reste sans dépendance vers `agent` (règle d'architecture, voir backlog).
    """
    proposal = await db.get(ActionProposal, proposal_id)
    if proposal is None or proposal.status != ActionStatus.PENDING:
        raise ActionNotFoundError(f"Proposition {proposal_id} introuvable ou déjà tranchée.")

    proposal.status = ActionStatus.APPROVED if decision == "approve" else ActionStatus.REJECTED
    # .replace(tzinfo=None) : la colonne est TIMESTAMP WITHOUT TIME ZONE, comme created_at
    # (server_default=func.now()) — asyncpg refuse un datetime aware sur une colonne naive.
    proposal.decided_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    await db.refresh(proposal)
    await write_log(
        db, "gating.decision", {"proposal_id": proposal_id, "decision": decision}, source="gating"
    )
    return proposal
