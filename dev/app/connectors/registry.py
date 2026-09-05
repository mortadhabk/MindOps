from dataclasses import dataclass

from app.connectors.base import Connector
from app.connectors.document.connector import DocumentConnector
from app.connectors.github.connector import GitHubConnector
from app.connectors.mock.connector import MockConnector
from app.connectors.sharepoint.connector import SharePointConnector
from app.core.exceptions import ConnectorNotFoundError

_CONNECTORS: dict[str, Connector] = {
    "document": DocumentConnector(),
    "github": GitHubConnector(),
    "mock": MockConnector(),
    "sharepoint": SharePointConnector(),
}


def get_connector(name: str) -> Connector:
    try:
        return _CONNECTORS[name]
    except KeyError:
        raise ConnectorNotFoundError(f"Connecteur inconnu : {name}") from None


def list_connectors() -> list[str]:
    return list(_CONNECTORS)


@dataclass
class ConnectorTypeInfo:
    """Métadonnées d'un type de connecteur, pour la palette et le formulaire du Studio (Epic 8)."""

    name: str
    display_name: str
    description: str
    config_schema: dict  # JSON Schema de Connector.config_schema


def list_connector_types() -> list[ConnectorTypeInfo]:
    return [
        ConnectorTypeInfo(
            name=connector.name,
            display_name=connector.display_name,
            description=connector.description,
            config_schema=connector.config_schema.model_json_schema(),
        )
        for connector in _CONNECTORS.values()
    ]
