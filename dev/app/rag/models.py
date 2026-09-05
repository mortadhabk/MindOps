from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.rag.embeddings.local import LocalMiniLMEmbeddingProvider


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(unique=True)
    content: Mapped[str]
    status: Mapped[str] = mapped_column(default="pending")
    # Instance de connecteur du Studio (Epic 8) à l'origine de ce document, si ingéré depuis là
    # plutôt que via POST /rag/ingest en direct. Référence par nom de table seulement (pas
    # d'import de app.connectors.models) : `rag` reste indépendant au niveau du code, mais
    # ON DELETE CASCADE fait supprimer ce document (et ses chunks, cascade déjà en place
    # ci-dessous) automatiquement quand l'instance de connecteur est supprimée dans le Studio.
    connector_instance_id: Mapped[int | None] = mapped_column(
        ForeignKey("connector_instances.id", ondelete="CASCADE"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    text: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(Vector(LocalMiniLMEmbeddingProvider.dimension))

    document: Mapped["Document"] = relationship(back_populates="chunks")
