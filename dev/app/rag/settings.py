from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.settings import store
from app.settings.registry import SettingsSection, register_section

SECTION_KEY = "rag"


class RagSettingsSchema(BaseModel):
    rag_chunk_max_tokens: int = Field(
        gt=0, description="Taille max d'un chunk, en mots (n'affecte que les futures ingestions)"
    )
    rag_chunk_overlap: int = Field(
        ge=0, description="Chevauchement entre chunks consécutifs, en mots"
    )
    rag_similarity_threshold: float = Field(
        ge=0, le=1, description="Score minimal pour qu'un résultat de recherche soit retenu"
    )
    rag_rerank_enabled: bool = Field(
        description=(
            "Réordonne les résultats de la recherche vectorielle avec un cross-encoder avant de "
            "les renvoyer — plus précis, un peu plus lent. N'affecte jamais le score affiché."
        )
    )


def get_effective_rag_settings() -> RagSettingsSchema:
    base = get_settings()
    override = store.get_override(SECTION_KEY) or {}
    return RagSettingsSchema(
        rag_chunk_max_tokens=override.get("rag_chunk_max_tokens", base.rag_chunk_max_tokens),
        rag_chunk_overlap=override.get("rag_chunk_overlap", base.rag_chunk_overlap),
        rag_similarity_threshold=override.get(
            "rag_similarity_threshold", base.rag_similarity_threshold
        ),
        rag_rerank_enabled=override.get("rag_rerank_enabled", base.rag_rerank_enabled),
    )


def _get_read_only() -> dict[str, Any]:
    base = get_settings()
    # Non éditable en V1 (décision actée, epic-9) : changer le modèle rendrait les vecteurs déjà
    # stockés incompatibles (dimension différente) sans une ré-ingestion complète. Même logique
    # pour le reranker : son modèle est un détail d'implémentation, pas un réglage utilisateur.
    return {
        "embedding_provider": base.embedding_provider,
        "embedding_model": base.embedding_model,
        "reranker_model": base.reranker_model,
    }


register_section(
    SettingsSection(
        key=SECTION_KEY,
        display_name="RAG (ingestion et recherche)",
        description=(
            "La taille et le chevauchement des chunks n'affectent que les prochaines "
            "ingestions — les documents déjà découpés ne sont pas retraités. Le seuil de "
            "similarité s'applique immédiatement à toute nouvelle recherche."
        ),
        schema=RagSettingsSchema,
        effect="immediate",
        get_current_values=lambda: get_effective_rag_settings().model_dump(),
        get_read_only=_get_read_only,
    )
)
