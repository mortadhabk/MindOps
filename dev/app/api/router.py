from fastapi import APIRouter

from app.agent.router import router as agent_router
from app.audit.router import router as audit_router
from app.connectors.router import router as connectors_router
from app.gating.router import router as gating_router
from app.rag.router import router as rag_router

router = APIRouter()
router.include_router(rag_router, prefix="/rag", tags=["rag"])
router.include_router(connectors_router, prefix="/connectors", tags=["connectors"])
router.include_router(agent_router, prefix="/agent", tags=["agent"])
router.include_router(gating_router, prefix="/gating", tags=["gating"])
router.include_router(audit_router, prefix="/audit", tags=["audit"])
