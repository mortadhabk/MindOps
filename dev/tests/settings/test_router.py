import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.core.database import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _override_db(db_session: AsyncSession):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()


async def test_list_sections_exposes_all_registered_domains(client: AsyncClient):
    response = await client.get("/settings/sections")

    assert response.status_code == 200
    keys = {s["key"] for s in response.json()}
    assert {"gating", "rag", "agent", "logging"}.issubset(keys)


async def test_rag_section_exposes_embedding_info_as_read_only(client: AsyncClient):
    response = await client.get("/settings/sections")

    rag_section = next(s for s in response.json() if s["key"] == "rag")
    assert "embedding_model" in rag_section["read_only"]
    assert "embedding_model" not in rag_section["config_schema"]["properties"]


async def test_update_section_persists_override_and_takes_effect_immediately(
    client: AsyncClient,
):
    response = await client.patch(
        "/settings/gating",
        json={"gating_policy": {"send_email": "auto_execute"}, "gating_min_confidence": 0.5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_override"] is True
    assert body["current_values"]["gating_policy"] == {"send_email": "auto_execute"}

    from app.gating.policy import Decision, evaluate

    assert evaluate("send_email", confidence=0.9) is Decision.AUTO_EXECUTE


async def test_update_section_rejects_invalid_payload(client: AsyncClient):
    response = await client.patch(
        "/settings/gating",
        json={"gating_policy": {}, "gating_min_confidence": 5},  # > 1 : invalide
    )

    assert response.status_code == 422


async def test_update_unknown_section_returns_404(client: AsyncClient):
    response = await client.patch("/settings/does-not-exist", json={})

    assert response.status_code == 404


async def test_reset_section_removes_the_override(client: AsyncClient):
    await client.patch(
        "/settings/rag",
        json={
            "rag_chunk_max_tokens": 50,
            "rag_chunk_overlap": 5,
            "rag_similarity_threshold": 0.5,
        },
    )

    response = await client.delete("/settings/rag")

    assert response.status_code == 200
    assert response.json()["has_override"] is False


async def test_reset_unknown_section_returns_404(client: AsyncClient):
    response = await client.delete("/settings/does-not-exist")

    assert response.status_code == 404


async def test_update_section_writes_an_audit_entry(client: AsyncClient, db_session: AsyncSession):
    marker = uuid.uuid4().hex
    await client.patch(
        "/settings/gating",
        json={"gating_policy": {"marker": marker}, "gating_min_confidence": 0.7},
    )

    stmt = select(AuditLog).where(AuditLog.event_type == "settings.updated")
    logs = (await db_session.execute(stmt)).scalars().all()
    assert any(
        log.payload.get("after", {}).get("gating_policy") == {"marker": marker} for log in logs
    )
