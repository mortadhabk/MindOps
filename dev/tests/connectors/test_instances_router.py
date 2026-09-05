import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors import instance_service
from app.connectors.router import get_sync_runner
from app.core.database import get_db
from app.main import app
from app.rag.embeddings import get_embedding_provider
from tests.rag.fakes import FakeEmbeddingProvider


@pytest.fixture(autouse=True)
def _override_dependencies(db_session: AsyncSession):
    async def _get_db():
        yield db_session

    synced_calls: list[int] = []

    async def _fake_sync_runner(instance_id: int, provider: object) -> None:
        synced_calls.append(instance_id)

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_embedding_provider] = FakeEmbeddingProvider
    app.dependency_overrides[get_sync_runner] = lambda: _fake_sync_runner
    app.state.synced_calls = synced_calls
    yield
    app.dependency_overrides.clear()


async def test_connector_types_exposes_config_schema(client: AsyncClient):
    response = await client.get("/connectors/types")

    assert response.status_code == 200
    types_by_name = {item["name"]: item for item in response.json()}
    assert types_by_name["github"]["display_name"] == "GitHub Issues"
    assert "site_url" in types_by_name["sharepoint"]["config_schema"]["properties"]


async def test_create_instance_then_list_it(client: AsyncClient):
    response = await client.post(
        "/connectors/instances",
        json={"connector_type": "mock", "display_name": "Ma source", "config": {}},
    )

    assert response.status_code == 201
    created = response.json()
    assert created["status"] == "idle"

    listing = await client.get("/connectors/instances")
    assert created["id"] in {i["id"] for i in listing.json()}


async def test_create_instance_rejects_invalid_config(client: AsyncClient):
    response = await client.post(
        "/connectors/instances",
        json={"connector_type": "github", "display_name": "Repo incomplet", "config": {}},
    )

    assert response.status_code == 422


async def test_create_instance_rejects_unknown_connector_type(client: AsyncClient):
    response = await client.post(
        "/connectors/instances",
        json={"connector_type": "does-not-exist", "display_name": "?", "config": {}},
    )

    assert response.status_code == 404


async def test_update_instance_position(client: AsyncClient, db_session: AsyncSession):
    instance = await instance_service.create_instance(
        db_session, connector_type="mock", display_name="Source", config={}
    )

    response = await client.patch(
        f"/connectors/instances/{instance.id}", json={"position_x": 10, "position_y": 20}
    )

    assert response.status_code == 200
    assert response.json()["position_x"] == 10


async def test_delete_instance(client: AsyncClient, db_session: AsyncSession):
    instance = await instance_service.create_instance(
        db_session, connector_type="mock", display_name="Source", config={}
    )

    response = await client.delete(f"/connectors/instances/{instance.id}")

    assert response.status_code == 204
    listing = await client.get("/connectors/instances")
    assert instance.id not in {i["id"] for i in listing.json()}


async def test_sync_instance_marks_syncing_and_triggers_the_background_runner(
    client: AsyncClient, db_session: AsyncSession
):
    instance = await instance_service.create_instance(
        db_session, connector_type="mock", display_name="Source", config={}
    )

    response = await client.post(f"/connectors/instances/{instance.id}/sync")

    assert response.status_code == 200
    assert response.json()["status"] == "syncing"
    assert app.state.synced_calls == [instance.id]


async def test_sync_unknown_instance_returns_404(client: AsyncClient):
    response = await client.post("/connectors/instances/999999/sync")

    assert response.status_code == 404
