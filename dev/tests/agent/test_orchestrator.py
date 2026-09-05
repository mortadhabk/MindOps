from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator import build_graph
from app.gating.models import ActionProposal, ActionStatus
from tests.agent.fakes import EchoTool, FakeSensitiveTool, ScriptedChatModel


@pytest.fixture
def echo_tool() -> EchoTool:
    return EchoTool()


@pytest.fixture
def sensitive_tool() -> FakeSensitiveTool:
    return FakeSensitiveTool()


def _set_gating_policy(monkeypatch, policy_map: dict[str, str], min_confidence: float = 0.8):
    fake_settings = SimpleNamespace(gating_policy=policy_map, gating_min_confidence=min_confidence)
    monkeypatch.setattr("app.gating.policy.get_settings", lambda: fake_settings)


def _sensitive_tool_call(call_id: str = "call-1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "fake_sensitive_action", "args": {"value": "x"}, "id": call_id}],
    )


async def test_agent_calls_tool_then_returns_final_answer(
    echo_tool: EchoTool, db_session: AsyncSession
):
    llm = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "echo", "args": {"text": "bonjour"}, "id": "call-1"}],
            ),
            AIMessage(content="Réponse finale basée sur l'outil."),
        ]
    )
    app = build_graph(llm, [echo_tool], MemorySaver(), db_session)

    result = await app.ainvoke(
        {"messages": [("user", "dis bonjour")]},
        config={"configurable": {"thread_id": "test-1"}},
    )

    assert echo_tool.calls == [{"text": "bonjour"}]
    assert result["messages"][-1].content == "Réponse finale basée sur l'outil."


async def test_agent_answers_directly_without_tool_call(
    echo_tool: EchoTool, db_session: AsyncSession
):
    llm = ScriptedChatModel(responses=[AIMessage(content="Pas besoin d'outil ici.")])
    app = build_graph(llm, [echo_tool], MemorySaver(), db_session)

    result = await app.ainvoke(
        {"messages": [("user", "bonjour")]},
        config={"configurable": {"thread_id": "test-2"}},
    )

    assert echo_tool.calls == []
    assert result["messages"][-1].content == "Pas besoin d'outil ici."


async def test_agent_remembers_history_across_turns(echo_tool: EchoTool, db_session: AsyncSession):
    llm = ScriptedChatModel(
        responses=[AIMessage(content="première réponse"), AIMessage(content="deuxième réponse")]
    )
    app = build_graph(llm, [echo_tool], MemorySaver(), db_session)
    config = {"configurable": {"thread_id": "test-3"}}

    await app.ainvoke({"messages": [("user", "premier message")]}, config=config)
    result = await app.ainvoke({"messages": [("user", "deuxième message")]}, config=config)

    stored_messages = [m.content for m in result["messages"]]
    assert "premier message" in stored_messages
    assert "deuxième réponse" == result["messages"][-1].content


async def test_agent_stops_when_llm_never_stops_calling_tools(
    echo_tool: EchoTool, db_session: AsyncSession
):
    always_calls_tool = AIMessage(
        content="", tool_calls=[{"name": "echo", "args": {"text": "boucle"}, "id": "call-x"}]
    )
    llm = ScriptedChatModel(responses=[always_calls_tool])
    app = build_graph(llm, [echo_tool], MemorySaver(), db_session)

    with pytest.raises(GraphRecursionError):
        await app.ainvoke(
            {"messages": [("user", "boucle infinie")]},
            config={"configurable": {"thread_id": "test-4"}, "recursion_limit": 6},
        )


# --- Epic 4 : politique de confiance, interrupt() et Command(resume=...) ---


async def test_agent_auto_execute_runs_without_interruption(
    sensitive_tool: FakeSensitiveTool, db_session: AsyncSession, monkeypatch
):
    _set_gating_policy(monkeypatch, {"fake_sensitive_action": "auto_execute"})
    llm = ScriptedChatModel(
        responses=[_sensitive_tool_call(), AIMessage(content="Action réalisée.")]
    )
    app = build_graph(llm, [sensitive_tool], MemorySaver(), db_session)
    config = {"configurable": {"thread_id": "gating-auto"}}

    result = await app.ainvoke({"messages": [("user", "fais l'action sensible")]}, config=config)

    assert sensitive_tool.delivered == ["x"]
    assert result["messages"][-1].content == "Action réalisée."

    proposal = (
        await db_session.execute(
            select(ActionProposal).where(ActionProposal.tool_call_id == "call-1")
        )
    ).scalar_one()
    assert proposal.status == ActionStatus.EXECUTED
    assert proposal.result == "livré: x"


async def test_agent_require_validation_pauses_the_graph(
    sensitive_tool: FakeSensitiveTool, db_session: AsyncSession, monkeypatch
):
    _set_gating_policy(monkeypatch, {})  # défaut : require_validation
    llm = ScriptedChatModel(responses=[_sensitive_tool_call()])
    app = build_graph(llm, [sensitive_tool], MemorySaver(), db_session)
    config = {"configurable": {"thread_id": "gating-pause"}}

    await app.ainvoke({"messages": [("user", "fais l'action sensible")]}, config=config)

    state = await app.aget_state(config)
    assert state.next != ()  # le graphe est bien suspendu, pas terminé
    assert state.interrupts  # un interrupt() est en attente de résolution
    assert sensitive_tool.delivered == []  # rien n'a été exécuté avant la validation humaine

    proposal = (
        await db_session.execute(
            select(ActionProposal).where(ActionProposal.tool_call_id == "call-1")
        )
    ).scalar_one()
    assert proposal.status == ActionStatus.PENDING
    assert state.interrupts[0].value["proposal_id"] == proposal.id


async def test_agent_resume_after_approval_executes_the_tool(
    sensitive_tool: FakeSensitiveTool, db_session: AsyncSession, monkeypatch
):
    _set_gating_policy(monkeypatch, {})
    llm = ScriptedChatModel(
        responses=[_sensitive_tool_call(), AIMessage(content="Email envoyé, tout est en ordre.")]
    )
    checkpointer = MemorySaver()
    app = build_graph(llm, [sensitive_tool], checkpointer, db_session)
    config = {"configurable": {"thread_id": "gating-resume-approve"}}
    await app.ainvoke({"messages": [("user", "fais l'action sensible")]}, config=config)

    # Simule gating.queue_service.decide(..., "approve") : seul le statut change en base,
    # exactement comme le ferait POST /gating/{id}/decide avant de déclencher la reprise.
    proposal = (
        await db_session.execute(
            select(ActionProposal).where(ActionProposal.tool_call_id == "call-1")
        )
    ).scalar_one()
    proposal.status = ActionStatus.APPROVED
    await db_session.commit()

    result = await app.ainvoke(Command(resume={"approved": True}), config=config)

    assert sensitive_tool.delivered == ["x"]
    assert result["messages"][-1].content == "Email envoyé, tout est en ordre."
    await db_session.refresh(proposal)
    assert proposal.status == ActionStatus.EXECUTED
    assert proposal.result == "livré: x"


async def test_agent_resume_after_rejection_never_executes(
    sensitive_tool: FakeSensitiveTool, db_session: AsyncSession, monkeypatch
):
    _set_gating_policy(monkeypatch, {})
    llm = ScriptedChatModel(
        responses=[_sensitive_tool_call(), AIMessage(content="Action annulée comme demandé.")]
    )
    checkpointer = MemorySaver()
    app = build_graph(llm, [sensitive_tool], checkpointer, db_session)
    config = {"configurable": {"thread_id": "gating-resume-reject"}}
    await app.ainvoke({"messages": [("user", "fais l'action sensible")]}, config=config)

    proposal = (
        await db_session.execute(
            select(ActionProposal).where(ActionProposal.tool_call_id == "call-1")
        )
    ).scalar_one()
    proposal.status = ActionStatus.REJECTED
    await db_session.commit()

    result = await app.ainvoke(Command(resume={"approved": False}), config=config)

    assert sensitive_tool.delivered == []  # jamais exécuté
    assert result["messages"][-1].content == "Action annulée comme demandé."
    await db_session.refresh(proposal)
    assert proposal.status == ActionStatus.REJECTED  # jamais passé à executed


async def test_agent_suggest_only_never_creates_a_proposal(
    sensitive_tool: FakeSensitiveTool, db_session: AsyncSession, monkeypatch
):
    _set_gating_policy(monkeypatch, {"fake_sensitive_action": "suggest_only"})
    llm = ScriptedChatModel(
        responses=[_sensitive_tool_call(), AIMessage(content="Je vous propose d'envoyer l'email.")]
    )
    app = build_graph(llm, [sensitive_tool], MemorySaver(), db_session)
    config = {"configurable": {"thread_id": "gating-suggest"}}

    result = await app.ainvoke({"messages": [("user", "fais l'action sensible")]}, config=config)

    assert sensitive_tool.delivered == []
    assert result["messages"][-1].content == "Je vous propose d'envoyer l'email."
    existing = (
        await db_session.execute(
            select(ActionProposal).where(ActionProposal.tool_call_id == "call-1")
        )
    ).scalar_one_or_none()
    assert existing is None
