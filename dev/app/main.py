from fastapi import FastAPI

from app.api.router import router as api_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestIDMiddleware, configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name)

app.add_middleware(RequestIDMiddleware)
register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
