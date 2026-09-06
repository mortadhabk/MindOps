from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.settings import store
from app.settings.registry import SettingsSection, register_section

SECTION_KEY = "gating"


class GatingSettingsSchema(BaseModel):
    gating_policy: dict[str, str] = Field(
        default_factory=dict,
        description="Décision par type d'action : suggest_only | require_validation | auto_execute",
        examples=[{"send_email": "require_validation"}],
    )
    gating_min_confidence: float = Field(
        ge=0,
        le=1,
        description="Confiance minimale pour laisser auto_execute s'appliquer (US-402)",
        examples=[0.8],
    )


def get_effective_gating_settings() -> GatingSettingsSchema:
    """Fusionne l'override (Epic 9) avec les valeurs par défaut de `.env` — appelée à chaque
    `policy.evaluate()`, donc un changement sauvegardé depuis l'UI s'applique dès le tour suivant
    de l'agent, sans redémarrage (démonstration US-406, enfin vraie de bout en bout)."""
    base = get_settings()
    override = store.get_override(SECTION_KEY) or {}
    return GatingSettingsSchema(
        gating_policy=override.get("gating_policy", base.gating_policy),
        gating_min_confidence=override.get("gating_min_confidence", base.gating_min_confidence),
    )


def _get_current_values() -> dict[str, Any]:
    return get_effective_gating_settings().model_dump()


register_section(
    SettingsSection(
        key=SECTION_KEY,
        display_name="Gating (politique de confiance)",
        description=(
            "Ajuste le curseur de confiance par type d'action, sans redémarrage — "
            "c'est la démonstration clé du projet (US-406)."
        ),
        schema=GatingSettingsSchema,
        effect="immediate",
        get_current_values=_get_current_values,
    )
)
