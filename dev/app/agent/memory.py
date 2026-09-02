from langgraph.checkpoint.memory import MemorySaver

# Historique de conversation en mémoire, indexé par thread_id (= conversation_id).
# Remplaçable par un checkpointer Postgres (langgraph-checkpoint-postgres) sans toucher
# à l'orchestrateur : c'est tout l'intérêt du checkpointer LangGraph.
checkpointer = MemorySaver()


def config_for(conversation_id: str) -> dict:
    return {"configurable": {"thread_id": conversation_id}}
