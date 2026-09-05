import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors import instance_service
from app.connectors.mock.connector import MockConnector
from app.core.exceptions import (
    ConnectorConfigError,
    ConnectorInstanceNotFoundError,
    ConnectorNotFoundError,
)
from tests.rag.fakes import FakeEmbeddingProvider


async def test_create_instance_validates_config_against_the_connector_schema(
    db_session: AsyncSession,
):
    with pytest.raises(ConnectorConfigError):  # "repo" manquant pour le schéma github
        await instance_service.create_instance(
            db_session,
            connector_type="github",
            display_name="Repo incomplet",
            config={"owner": "acme"},
        )


async def test_create_instance_raises_for_unknown_connector_type(db_session: AsyncSession):
    with pytest.raises(ConnectorNotFoundError):
        await instance_service.create_instance(
            db_session, connector_type="does-not-exist", display_name="?", config={}
        )


async def test_create_then_list_instances(db_session: AsyncSession):
    created = await instance_service.create_instance(
        db_session,
        connector_type="mock",
        display_name="Source de test",
        config={},
        position_x=12.5,
        position_y=40,
    )

    instances = await instance_service.list_instances(db_session)

    assert created.status == "idle"
    assert [i.id for i in instances] == [created.id]
    assert instances[0].position_x == 12.5


async def test_update_position_persists_new_coordinates(db_session: AsyncSession):
    instance = await instance_service.create_instance(
        db_session, connector_type="mock", display_name="Source", config={}
    )

    updated = await instance_service.update_position(
        db_session, instance.id, position_x=100, position_y=200
    )

    assert updated.position_x == 100
    assert updated.position_y == 200


async def test_update_position_raises_for_unknown_instance(db_session: AsyncSession):
    with pytest.raises(ConnectorInstanceNotFoundError):
        await instance_service.update_position(db_session, 999_999, position_x=0, position_y=0)


async def test_delete_instance_removes_it(db_session: AsyncSession):
    instance = await instance_service.create_instance(
        db_session, connector_type="mock", display_name="Source", config={}
    )

    await instance_service.delete_instance(db_session, instance.id)

    assert await instance_service.list_instances(db_session) == []


async def test_delete_instance_raises_for_unknown_instance(db_session: AsyncSession):
    with pytest.raises(ConnectorInstanceNotFoundError):
        await instance_service.delete_instance(db_session, 999_999)


async def test_mark_syncing_updates_status(db_session: AsyncSession):
    instance = await instance_service.create_instance(
        db_session, connector_type="mock", display_name="Source", config={}
    )

    updated = await instance_service.mark_syncing(db_session, instance.id)

    assert updated.status == "syncing"


async def test_run_sync_ingests_items_and_marks_success(db_session: AsyncSession):
    instance = await instance_service.create_instance(
        db_session, connector_type="mock", display_name="Source", config={}
    )

    await instance_service.run_sync(db_session, instance.id, FakeEmbeddingProvider())

    await db_session.refresh(instance)
    assert instance.status == "success"
    assert instance.last_result == {"synced": 2, "errors": []}
    assert instance.last_synced_at is not None


async def test_run_sync_marks_error_when_the_connector_itself_fails(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    async def _boom(self, **params):
        raise RuntimeError("source injoignable")

    monkeypatch.setattr(MockConnector, "fetch_items", _boom)

    instance = await instance_service.create_instance(
        db_session, connector_type="mock", display_name="Source en panne", config={}
    )

    await instance_service.run_sync(db_session, instance.id, FakeEmbeddingProvider())

    await db_session.refresh(instance)
    assert instance.status == "error"
    assert instance.last_result == {"synced": 0, "errors": ["source injoignable"]}
