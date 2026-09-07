import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import memory as agent_memory
from app.agent.conversation_service import touch_conversation
from app.agent.llm_client import get_llm_client
from app.agent.memory import config_for
from app.agent.models import Conversation
from app.agent.orchestrator import AgentStreamError, build_graph, extract_message_text, stream_chat
from app.agent.schemas import ChatRequest, ConversationMessageOut, ConversationOut
from app.agent.tools.search_knowledge import SearchKnowledgeTool
from app.agent.tools.send_email import SendEmailTool
from app.core.database import get_db
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.reranking import Reranker, get_reranker

router = APIRouter()


def get_checkpointer() -> BaseCheckpointSaver:
    # Lit `agent_memory.checkpointer` au moment de l'appel (pas à l'import) : sa valeur passe de
    # None à l'instance réelle pendant le lifespan FastAPI (voir app/main.py). Cette indirection
    # sert aussi les tests (tests/agent/test_router.py), qui tournent hors lifespan et remplacent
    # ce provider par un MemorySaver via dependency_overrides.
    if agent_memory.checkpointer is None:
        raise RuntimeError("Checkpointer non initialisé — init_checkpointer() n'a pas tourné.")
    return agent_memory.checkpointer


async def _sse_events(app, *, conversation_id: str, message: str) -> AsyncIterator[str]:
    yield f"event: start\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"
    try:
        async for token in stream_chat(app, conversation_id=conversation_id, user_message=message):
            yield f"event: delta\ndata: {json.dumps({'text': token})}\n\n"
    except AgentStreamError as exc:
        # Sans ce garde-fou, une panne fournisseur (clé refusée, réseau, ...) coupait le flux
        # SSE en silence : le front restait en "pending" indéfiniment, faute de `done` ou
        # `pending_approval` pour le signaler (voir conversation support).
        yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
        return

    # Le graphe peut s'être arrêté normalement OU s'être interrompu (Epic 4, outil sensible
    # en attente de validation) — dans ce second cas, astream() se termine sans erreur, donc
    # c'est ici, après coup, qu'on distingue les deux issues via l'état persisté.
    state = await app.aget_state({"configurable": {"thread_id": conversation_id}})
    if state.interrupts:
        proposal_id = state.interrupts[0].value.get("proposal_id")
        payload = {"conversation_id": conversation_id, "proposal_id": proposal_id}
        yield f"event: pending_approval\ndata: {json.dumps(payload)}\n\n"
    else:
        yield "event: done\ndata: {}\n\n"


@router.post(
    "/chat",
    summary="Discuter avec l'agent",
    description=(
        "Envoie un message à l'agent et streame la réponse en Server-Sent Events. "
        "`conversation_id` (optionnel) permet de poursuivre une conversation existante. "
        "Si l'agent propose une action sensible nécessitant une validation (Epic 4), le flux "
        "se termine par `event: pending_approval` au lieu de `event: done` — voir `/gating`."
    ),
)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
    llm: BaseChatModel = Depends(get_llm_client),
    checkpointer: BaseCheckpointSaver = Depends(get_checkpointer),
    reranker: Reranker = Depends(get_reranker),
) -> StreamingResponse:
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    await touch_conversation(db, conversation_id, payload.message)
    tools = [
        SearchKnowledgeTool(db=db, provider=provider, reranker=reranker),
        SendEmailTool(),
    ]
    app = build_graph(llm, tools, checkpointer, db)

    return StreamingResponse(
        _sse_events(app, conversation_id=conversation_id, message=payload.message),
        media_type="text/event-stream",
    )


@router.get(
    "/conversations",
    summary="Lister les conversations passées",
    response_model=list[ConversationOut],
)
async def list_conversations(db: AsyncSession = Depends(get_db)) -> list[ConversationOut]:
    result = await db.execute(select(Conversation).order_by(Conversation.updated_at.desc()))
    return [ConversationOut.model_validate(conv) for conv in result.scalars()]


@router.get(
    "/conversations/{conversation_id}/messages",
    summary="Récupérer les messages d'une conversation passée",
    description=(
        "Reconstruit l'historique depuis le checkpoint LangGraph — seuls les tours "
        "utilisateur/assistant avec du texte sont renvoyés (les appels d'outils internes sont "
        "omis, ils ne font pas sens hors contexte d'exécution)."
    ),
    response_model=list[ConversationMessageOut],
)
async def get_conversation_messages(
    conversation_id: str, checkpointer: BaseCheckpointSaver = Depends(get_checkpointer)
) -> list[ConversationMessageOut]:
    checkpoint_tuple = await checkpointer.aget_tuple(config_for(conversation_id))
    if checkpoint_tuple is None:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    messages = checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
    out: list[ConversationMessageOut] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage):
            role = "assistant"
        else:
            continue
        text = extract_message_text(message.content)
        if text:
            out.append(ConversationMessageOut(role=role, text=text))
    return out
