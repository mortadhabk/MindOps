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
    # Surcharge `schema.model_json_schema()` quand un champ dépend d'un état dynamique (ex : la
    # liste des types de fournisseurs LLM disponibles, injectée en `enum`).
    get_config_schema: Callable[[], dict[str, Any]] | None = None
    # Transforme les valeurs validées juste avant persistance — reçoit (nouvelles valeurs,
    # override existant ou None). Utilisé pour les champs secrets (Epic 9, interface-first) :
    # chiffrer une nouvelle valeur non vide, ou conserver le secret déjà stocké si le champ est
    # soumis vide (« ne pas changer »).
    pre_store: Callable[[dict[str, Any], dict[str, Any] | None], dict[str, Any]] | None = None

    def json_schema(self) -> dict[str, Any]:
        if self.get_config_schema:
            return self.get_config_schema()
        return self.schema.model_json_schema()


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
