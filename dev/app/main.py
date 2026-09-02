from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.router import router as api_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestIDMiddleware, configure_logging

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
    ],
)

app.add_middleware(RequestIDMiddleware)
register_exception_handlers(app)
app.include_router(api_router)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["infra"], summary="Vérifier que l'API répond")
async def health() -> dict[str, str]:
    return {"status": "ok"}
