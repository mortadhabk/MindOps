from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

import app.agent.settings  # noqa: F401  effet de bord : register_section au chargement
import app.core.logging_settings  # noqa: F401  idem
import app.gating.settings  # noqa: F401  idem
import app.rag.settings  # noqa: F401  idem
from app.audit.service import write_log
from app.core.database import get_db
from app.core.exceptions import SettingsValidationError
from app.settings import store
from app.settings.registry import SettingsSection, get_section, list_sections
from app.settings.schemas import SettingsSectionOut

router = APIRouter()


def _to_out(section: SettingsSection) -> SettingsSectionOut:
    return SettingsSectionOut(
        key=section.key,
        display_name=section.display_name,
        description=section.description,
        effect=section.effect,
        config_schema=section.schema.model_json_schema(),
        current_values=section.get_current_values(),
        read_only=section.get_read_only(),
        has_override=store.get_override(section.key) is not None,
    )


@router.get(
    "/sections",
    response_model=list[SettingsSectionOut],
    summary="Lister les sections de paramétrage éditables",
    description=(
        "Alimente l'onglet Paramètres (Epic 9) : chaque section porte son schéma de "
        "configuration (JSON Schema), sa valeur effective actuelle, et d'éventuelles "
        "informations en lecture seule (ex : modèle d'embeddings, alias d'identifiants)."
    ),
)
async def list_settings_sections() -> list[SettingsSectionOut]:
    return [_to_out(section) for section in list_sections()]


@router.patch(
    "/{key}",
    response_model=SettingsSectionOut,
    summary="Modifier une section de paramétrage",
    description=(
        "Valide `value` contre le schéma de la section, persiste l'override, applique "
        "immédiatement les effets de bord nécessaires (ex : invalider le client LLM en cache) "
        "et journalise le changement dans l'audit (`settings.updated`)."
    ),
)
async def update_settings_section(
    key: str,
    value: dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
) -> SettingsSectionOut:
    section = get_section(key)  # lève SettingsSectionNotFoundError si inconnue
    try:
        validated = section.schema.model_validate(value).model_dump()
    except ValidationError as exc:
        raise SettingsValidationError(
            f"Configuration invalide pour la section « {key} »",
            details={"errors": exc.errors(include_url=False, include_context=False)},
        ) from exc

    before = section.get_current_values()
    await store.set_override(db, key, validated)
    if section.apply is not None:
        section.apply(validated)
    await write_log(
        db,
        "settings.updated",
        {"section": key, "before": before, "after": validated},
        source="settings",
    )
    return _to_out(section)


@router.delete(
    "/{key}",
    response_model=SettingsSectionOut,
    summary="Réinitialiser une section à sa valeur par défaut (.env)",
)
async def reset_settings_section(
    key: str, db: AsyncSession = Depends(get_db)
) -> SettingsSectionOut:
    section = get_section(key)
    before = section.get_current_values()
    await store.clear_override(db, key)
    after = section.get_current_values()
    if section.apply is not None:
        section.apply(after)
    await write_log(db, "settings.reset", {"section": key, "before": before}, source="settings")
    return _to_out(section)
