import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.language_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm_client import get_llm_client
from app.agent.memory import checkpointer
from app.agent.orchestrator import build_graph, stream_chat
from app.agent.schemas import ChatRequest
from app.agent.tools.search_knowledge import SearchKnowledgeTool
from app.agent.tools.send_email import SendEmailTool
from app.core.database import get_db
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider

router = APIRouter()


async def _sse_events(app, *, conversation_id: str, message: str) -> AsyncIterator[str]:
    yield f"event: start\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"
    async for token in stream_chat(app, conversation_id=conversation_id, user_message=message):
        yield f"event: delta\ndata: {json.dumps({'text': token})}\n\n"

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
) -> StreamingResponse:
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    tools = [SearchKnowledgeTool(db=db, provider=provider), SendEmailTool()]
    app = build_graph(llm, tools, checkpointer, db)

    return StreamingResponse(
        _sse_events(app, conversation_id=conversation_id, message=payload.message),
        media_type="text/event-stream",
    )
