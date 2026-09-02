import pytest

from app.connectors.github.connector import GitHubConnector
from app.connectors.mock.connector import MockConnector
from app.connectors.registry import get_connector, list_connectors
from app.core.exceptions import ConnectorNotFoundError


def test_list_connectors_includes_registered_names():
    assert set(list_connectors()) == {"github", "mock"}


def test_get_connector_returns_matching_implementation():
    assert isinstance(get_connector("github"), GitHubConnector)
    assert isinstance(get_connector("mock"), MockConnector)


def test_get_connector_raises_for_unknown_name():
    with pytest.raises(ConnectorNotFoundError):
        get_connector("does-not-exist")
