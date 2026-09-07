from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Conversation(Base):
    """Métadonnées d'une conversation (titre, dates) pour la sidebar historique — les messages
    eux-mêmes vivent dans les checkpoints LangGraph (app/agent/memory.py), pas ici : `id` est le
    même thread_id que celui passé au checkpointer, ce qui relie les deux sans duplication."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
