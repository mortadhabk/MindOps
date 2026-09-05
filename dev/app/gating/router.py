from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.gating import queue_service
from app.gating.schemas import ActionProposalOut, DecisionIn

router = APIRouter()

GraphResumer = Callable[[int], Awaitable[None]]


async def _default_resumer(proposal_id: int) -> None:
    """Implémentation par défaut (no-op). `main.py` (composition root) la remplace par
    l'adaptateur réel `agent.resume_service.resume_agent_graph` via `dependency_overrides`,
    pour que `gating` n'importe jamais `agent` — cf. la règle de dépendance du backlog
    (`agent → rag, gating, audit`, jamais l'inverse)."""


def get_graph_resumer() -> GraphResumer:
    return _default_resumer


@router.get(
    "/pending",
    response_model=list[ActionProposalOut],
    summary="Lister les actions en attente de validation",
)
async def pending(db: AsyncSession = Depends(get_db)) -> list[ActionProposalOut]:
    proposals = await queue_service.list_pending(db)
    return [ActionProposalOut.model_validate(proposal) for proposal in proposals]


@router.post(
    "/{proposal_id}/decide",
    response_model=ActionProposalOut,
    summary="Approuver ou rejeter une action proposée",
    description=(
        "Met à jour le statut de la proposition puis reprend le graphe LangGraph interrompu "
        "(US-405). `approve` déclenche l'exécution réelle de l'outil ; `reject` débloque le "
        "graphe sans jamais exécuter l'action — dans les deux cas l'agent reprend la conversation."
    ),
)
async def decide(
    proposal_id: int,
    payload: DecisionIn,
    db: AsyncSession = Depends(get_db),
    resume: GraphResumer = Depends(get_graph_resumer),
) -> ActionProposalOut:
    proposal = await queue_service.decide(db, proposal_id, payload.decision)
    await resume(proposal_id)
    await db.refresh(proposal)
    return ActionProposalOut.model_validate(proposal)
