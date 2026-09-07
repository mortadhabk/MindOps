from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from app.config import get_settings

# Historique de conversation persisté en base (Postgres), indexé par thread_id (= conversation_id)
# — remplace le MemorySaver initial (perdu à chaque redémarrage) pour que la sidebar de l'historique
# des conversations survive aux redéploiements. `None` jusqu'à `init_checkpointer()` : la classe
# `AsyncPostgresSaver` capture la boucle asyncio courante à la construction (`get_running_loop()`),
# donc impossible de l'instancier au simple import du module — il faut attendre le lifespan FastAPI
# (app/main.py), qui tourne bien dans une boucle active.
checkpointer: BaseCheckpointSaver | None = None
_pool: AsyncConnectionPool | None = None


async def init_checkpointer() -> None:
    global checkpointer, _pool
    _pool = AsyncConnectionPool(
        conninfo=get_settings().psycopg_database_url,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=False,
    )
    await _pool.open()
    checkpointer = AsyncPostgresSaver(_pool)
    await checkpointer.setup()


def config_for(conversation_id: str) -> dict:
    return {"configurable": {"thread_id": conversation_id}}
