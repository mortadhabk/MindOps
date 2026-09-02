from app.connectors.base import Connector
from app.connectors.github.connector import GitHubConnector
from app.connectors.mock.connector import MockConnector
from app.core.exceptions import ConnectorNotFoundError

_CONNECTORS: dict[str, Connector] = {
    "github": GitHubConnector(),
    "mock": MockConnector(),
}


def get_connector(name: str) -> Connector:
    try:
        return _CONNECTORS[name]
    except KeyError:
        raise ConnectorNotFoundError(f"Connecteur inconnu : {name}") from None


def list_connectors() -> list[str]:
    return list(_CONNECTORS)
