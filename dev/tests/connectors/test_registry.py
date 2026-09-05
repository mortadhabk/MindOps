import pytest

from app.connectors.github.connector import GitHubConnector
from app.connectors.mock.connector import MockConnector
from app.connectors.registry import get_connector, list_connector_types, list_connectors
from app.connectors.sharepoint.connector import SharePointConnector
from app.core.exceptions import ConnectorNotFoundError


def test_list_connectors_includes_registered_names():
    assert set(list_connectors()) == {"github", "mock", "sharepoint"}


def test_get_connector_returns_matching_implementation():
    assert isinstance(get_connector("github"), GitHubConnector)
    assert isinstance(get_connector("mock"), MockConnector)
    assert isinstance(get_connector("sharepoint"), SharePointConnector)


def test_get_connector_raises_for_unknown_name():
    with pytest.raises(ConnectorNotFoundError):
        get_connector("does-not-exist")


def test_list_connector_types_exposes_config_schema_for_the_studio():
    types_by_name = {info.name: info for info in list_connector_types()}

    github_type = types_by_name["github"]
    assert github_type.display_name == "GitHub Issues"
    assert set(github_type.config_schema["required"]) == {"owner", "repo"}

    sharepoint_type = types_by_name["sharepoint"]
    assert "site_url" in sharepoint_type.config_schema["properties"]
