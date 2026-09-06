from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.settings.models import AppSetting

# Cache mémoire, tenu à jour en écriture (write-through) : évite une lecture DB à chaque appel de
# get_settings()-équivalent dans gating/rag/agent, qui tournent à chaque tour de l'agent. Limite
# assumée : un seul processus uvicorn pour ce POC, pas de synchronisation multi-réplica.
_overrides: dict[str, dict[str, Any]] = {}


async def load_overrides(db: AsyncSession) -> None:
    """Appelé une fois au démarrage de l'application (voir app/main.py)."""
    result = await db.execute(select(AppSetting))
    _overrides.clear()
    for row in result.scalars():
        _overrides[row.section] = row.value


def get_override(section: str) -> dict[str, Any] | None:
    return _overrides.get(section)


async def set_override(db: AsyncSession, section: str, value: dict[str, Any]) -> None:
    existing = await db.get(AppSetting, section)
    if existing is None:
        db.add(AppSetting(section=section, value=value))
    else:
        existing.value = value
    await db.commit()
    _overrides[section] = value


async def clear_override(db: AsyncSession, section: str) -> None:
    existing = await db.get(AppSetting, section)
    if existing is not None:
        await db.delete(existing)
        await db.commit()
    _overrides.pop(section, None)
