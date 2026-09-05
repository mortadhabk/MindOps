from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.agent.resume_service import resume_agent_graph
from app.api.router import router as api_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestIDMiddleware, configure_logging
from app.gating.router import get_graph_resumer

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    description=(
        "Socle agentique modulaire (RAG + connecteurs + orchestration + gating) — POC. "
        "Documentation complète par module dans docs/."
    ),
    version="0.1.0",
    openapi_tags=[
        {"name": "infra", "description": "Endpoints d'infrastructure (santé, ...)"},
        {"name": "rag", "description": "Ingestion et recherche sémantique (Epic 1)"},
        {"name": "connectors", "description": "Synchronisation des sources externes (Epic 2)"},
        {"name": "agent", "description": "Orchestrateur agentique, chat en streaming (Epic 3)"},
        {"name": "gating", "description": "Politique de confiance et validation humaine (Epic 4)"},
    ],
)

app.add_middleware(RequestIDMiddleware)
register_exception_handlers(app)
app.include_router(api_router)

# Composition root (Ports & Adapters) : gating.router expose un port GraphResumer sans jamais
# importer `agent` (règle de dépendance) ; c'est ici, à l'unique endroit où les deux modules se
# rencontrent, que l'adaptateur concret est branché derrière l'interface.
app.dependency_overrides[get_graph_resumer] = lambda: resume_agent_graph


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["infra"], summary="Vérifier que l'API répond")
async def health() -> dict[str, str]:
    return {"status": "ok"}
