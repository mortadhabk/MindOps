from datetime import datetime

from sqlalchemy import JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConnectorInstance(Base):
    """Une source configurée par l'utilisateur depuis le Studio (Epic 8) : un nœud du canvas."""

    __tablename__ = "connector_instances"

    id: Mapped[int] = mapped_column(primary_key=True)
    connector_type: Mapped[str]  # clé du registry, ex: "github", "sharepoint"
    display_name: Mapped[str]  # nom choisi par l'utilisateur, ex: "Repo backend"
    config: Mapped[dict] = mapped_column(JSON)  # validé par Connector.config_schema à l'écriture
    position_x: Mapped[float] = mapped_column(default=0)
    position_y: Mapped[float] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(default="idle")  # idle | syncing | success | error
    last_synced_at: Mapped[datetime | None] = mapped_column(default=None)
    last_result: Mapped[dict | None] = mapped_column(JSON, default=None)  # {synced, errors}
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
