from datetime import datetime

from sqlalchemy import JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str]  # ex: "agent.llm_call", "agent.action_proposed", "gating.decision"
    source: Mapped[str]  # module d'origine de l'événement, ex: "agent", "gating"
    payload: Mapped[dict] = mapped_column(JSON)
    result: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
