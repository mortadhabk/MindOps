import json

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm_client import get_llm_client
from app.agent.router import get_checkpointer
from app.core.database import get_db
from app.main import app
from app.rag.embeddings import get_embedding_provider
from tests.agent.fakes import ScriptedChatModel
from tests.rag.fakes import FakeEmbeddingProvider


@pytest.fixture(autouse=True)
def _override_dependencies(db_session: AsyncSession):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_embedding_provider] = FakeEmbeddingProvider
    # MemorySaver plutôt que le checkpointer Postgres réel : les tests tournent hors du lifespan
    # FastAPI (voir app/main.py), donc son pool de connexions n'est jamais ouvert. Une seule
    # instance partagée par test (pas la classe brute) pour que l'historique survive entre
    # plusieurs appels HTTP d'un même test, comme le ferait le singleton réel en production.
    test_checkpointer = MemorySaver()
    app.dependency_overrides[get_checkpointer] = lambda: test_checkpointer
    yield
    app.dependency_overrides.clear()


def _override_llm(llm: ScriptedChatModel) -> None:
    app.dependency_overrides[get_llm_client] = lambda: llm


async def _parse_sse_deltas(text: str) -> str:
    deltas = []
    for block in text.split("\n\n"):
        if block.startswith("event: delta"):
            data_line = next(line for line in block.splitlines() if line.startswith("data: "))
            deltas.append(json.loads(data_line[len("data: ") :])["text"])
    return "".join(deltas)


async def test_chat_cites_knowledge_base_via_search_knowledge_tool(db_session: AsyncSession):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/rag/ingest",
            json={
                "source": "test-suite",
                "content": "Le service de paiement echoue en production depuis ce matin",
            },
        )

        llm = ScriptedChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "search_knowledge", "args": {"query": "paiement"}, "id": "c1"}
                    ],
                ),
                AIMessage(
                    content="Le paiement echoue en production, voir la base de connaissances."
                ),
            ]
        )
        _override_llm(llm)

        response = await client.post(
            "/agent/chat", json={"conversation_id": "conv-test", "message": "pourquoi ca echoue ?"}
        )

        assert response.status_code == 200
        full_text = await _parse_sse_deltas(response.text)
        assert full_text == "Le paiement echoue en production, voir la base de connaissances."


async def test_chat_answers_directly_without_tool_call():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        llm = ScriptedChatModel(responses=[AIMessage(content="Bonjour !")])
        _override_llm(llm)

        response = await client.post("/agent/chat", json={"message": "salut"})

        assert response.status_code == 200
        full_text = await _parse_sse_deltas(response.text)
        assert full_text == "Bonjour !"


async def test_list_conversations_returns_most_recent_first(db_session: AsyncSession):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        _override_llm(ScriptedChatModel(responses=[AIMessage(content="Bonjour !")]))
        await client.post("/agent/chat", json={"conversation_id": "conv-a", "message": "salut"})
        _override_llm(ScriptedChatModel(responses=[AIMessage(content="Ça marche.")]))
        await client.post(
            "/agent/chat", json={"conversation_id": "conv-b", "message": "ça marche ?"}
        )

        response = await client.get("/agent/conversations")

        assert response.status_code == 200
        # Filtré aux deux ids du test : la base partagée par les tests (voir db_session dans
        # conftest.py) peut porter d'autres conversations issues d'essais manuels antérieurs.
        relevant = [conv for conv in response.json() if conv["id"] in ("conv-a", "conv-b")]
        assert [conv["id"] for conv in relevant] == ["conv-b", "conv-a"]
        assert relevant[0]["title"] == "ça marche ?"


async def test_get_conversation_messages_returns_user_and_assistant_turns(
    db_session: AsyncSession,
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        _override_llm(ScriptedChatModel(responses=[AIMessage(content="Bonjour !")]))
        await client.post(
            "/agent/chat", json={"conversation_id": "conv-history", "message": "salut"}
        )

        response = await client.get("/agent/conversations/conv-history/messages")

        assert response.status_code == 200
        assert response.json() == [
            {"role": "user", "text": "salut"},
            {"role": "assistant", "text": "Bonjour !"},
        ]


async def test_get_conversation_messages_404_for_unknown_conversation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/agent/conversations/does-not-exist/messages")

        assert response.status_code == 404
