from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

from app.core.exceptions import SettingsSectionNotFoundError

Effect = Literal["immediate", "deferred"]


@dataclass
class SettingsSection:
    """Un domaine de paramétrage éditable depuis l'onglet Paramètres (Epic 9).

    Généralisation du pattern `Connector.config_schema` (Epic 8) : chaque module déclare son
    propre schéma, plutôt que de centraliser la définition des champs dans ce fichier.
    """

    key: str
    display_name: str
    description: str
    schema: type[BaseModel]
    effect: Effect
    get_current_values: Callable[[], dict[str, Any]]
    get_read_only: Callable[[], dict[str, Any]] = field(default=lambda: {})
    # Effet de bord après sauvegarde/réinitialisation (ex: invalider un client mis en cache) —
    # None quand le module relit déjà la config à chaque appel (gating, rag : rien à faire).
    apply: Callable[[dict[str, Any]], None] | None = None


_SECTIONS: dict[str, SettingsSection] = {}


def register_section(section: SettingsSection) -> None:
    _SECTIONS[section.key] = section


def get_section(key: str) -> SettingsSection:
    try:
        return _SECTIONS[key]
    except KeyError:
        raise SettingsSectionNotFoundError(f"Section de paramétrage inconnue : {key}") from None


def list_sections() -> list[SettingsSection]:
    return list(_SECTIONS.values())
