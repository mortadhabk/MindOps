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
from app.core.database import get_db
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider

router = APIRouter()


async def _sse_events(app, *, conversation_id: str, message: str) -> AsyncIterator[str]:
    yield f"event: start\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"
    async for token in stream_chat(app, conversation_id=conversation_id, user_message=message):
        yield f"event: delta\ndata: {json.dumps({'text': token})}\n\n"
    yield "event: done\ndata: {}\n\n"


@router.post(
    "/chat",
    summary="Discuter avec l'agent",
    description=(
        "Envoie un message à l'agent et streame la réponse en Server-Sent Events. "
        "`conversation_id` (optionnel) permet de poursuivre une conversation existante."
    ),
)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
    llm: BaseChatModel = Depends(get_llm_client),
) -> StreamingResponse:
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    tools = [SearchKnowledgeTool(db=db, provider=provider)]
    app = build_graph(llm, tools, checkpointer)

    return StreamingResponse(
        _sse_events(app, conversation_id=conversation_id, message=payload.message),
        media_type="text/event-stream",
    )
