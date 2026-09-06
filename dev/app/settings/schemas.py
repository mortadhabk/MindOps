from typing import Any

from pydantic import BaseModel, Field

from app.settings.registry import Effect


class SettingsSectionOut(BaseModel):
    key: str = Field(examples=["gating"])
    display_name: str = Field(examples=["Gating (politique de confiance)"])
    description: str
    effect: Effect = Field(
        description="'immediate' : pris en compte dès la sauvegarde. "
        "'deferred' : à la prochaine requête concernée (ex: prochain message pour le LLM)."
    )
    config_schema: dict = Field(description="JSON Schema des champs éditables")
    current_values: dict[str, Any] = Field(description="Valeurs effectives (override ou défaut)")
    read_only: dict[str, Any] = Field(
        default_factory=dict, description="Informations affichées mais non éditables depuis l'UI"
    )
    has_override: bool = Field(description="False si la section utilise encore la valeur .env")
