from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.logging import configure_logging
from app.settings import store
from app.settings.registry import SettingsSection, register_section

SECTION_KEY = "logging"


class LoggingSettingsSchema(BaseModel):
    log_level: str = Field(
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Niveau de log du serveur",
        examples=["INFO"],
    )


def get_effective_log_level() -> str:
    base = get_settings()
    override = store.get_override(SECTION_KEY) or {}
    return override.get("log_level", base.log_level).upper()


def _apply(values: dict[str, Any]) -> None:
    configure_logging(values["log_level"])


register_section(
    SettingsSection(
        key=SECTION_KEY,
        display_name="Journalisation",
        description="Niveau de log appliqué immédiatement, sans redémarrage.",
        schema=LoggingSettingsSchema,
        effect="immediate",
        get_current_values=lambda: {"log_level": get_effective_log_level()},
        apply=_apply,
    )
)
