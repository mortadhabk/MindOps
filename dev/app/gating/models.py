from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ActionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class ActionProposal(Base):
    __tablename__ = "action_proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    action_type: Mapped[str]  # nom du Tool concerné, ex: "send_email"
    parameters: Mapped[dict] = mapped_column(JSON)  # args validés par le args_schema de l'outil
    status: Mapped[ActionStatus] = mapped_column(
        SAEnum(ActionStatus, native_enum=False, length=32), default=ActionStatus.PENDING
    )
    conversation_id: Mapped[str]  # = thread_id LangGraph, pour reprendre le bon graphe
    tool_call_id: Mapped[str] = mapped_column(unique=True)  # id d'appel outil du LLM (idempotence)
    result: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(default=None)
    executed_at: Mapped[datetime | None] = mapped_column(default=None)
