from sqlalchemy.ext.asyncio import AsyncSession

from app.settings import store
from app.settings.models import AppSetting


async def test_set_override_persists_and_updates_memory_cache(db_session: AsyncSession):
    await store.set_override(
        db_session, "gating", {"gating_policy": {}, "gating_min_confidence": 0.9}
    )

    assert store.get_override("gating") == {"gating_policy": {}, "gating_min_confidence": 0.9}
    row = await db_session.get(AppSetting, "gating")
    assert row is not None
    assert row.value == {"gating_policy": {}, "gating_min_confidence": 0.9}


async def test_set_override_updates_an_existing_row_instead_of_duplicating(
    db_session: AsyncSession,
):
    await store.set_override(db_session, "gating", {"a": 1})
    await store.set_override(db_session, "gating", {"a": 2})

    assert store.get_override("gating") == {"a": 2}
    row = await db_session.get(AppSetting, "gating")
    assert row.value == {"a": 2}


async def test_clear_override_removes_it_from_db_and_memory(db_session: AsyncSession):
    await store.set_override(db_session, "gating", {"x": 1})

    await store.clear_override(db_session, "gating")

    assert store.get_override("gating") is None
    assert await db_session.get(AppSetting, "gating") is None


async def test_clear_override_is_a_noop_when_nothing_was_set(db_session: AsyncSession):
    await store.clear_override(db_session, "does-not-exist")  # ne doit pas lever

    assert store.get_override("does-not-exist") is None


async def test_load_overrides_populates_memory_from_db(db_session: AsyncSession):
    await store.set_override(db_session, "rag", {"y": 2})
    store._overrides.clear()  # simule un redémarrage : cache mémoire vide

    await store.load_overrides(db_session)

    assert store.get_override("rag") == {"y": 2}
