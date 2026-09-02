import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError

from app.agent.orchestrator import build_graph
from tests.agent.fakes import EchoTool, ScriptedChatModel


@pytest.fixture
def echo_tool() -> EchoTool:
    return EchoTool()


async def test_agent_calls_tool_then_returns_final_answer(echo_tool: EchoTool):
    llm = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "echo", "args": {"text": "bonjour"}, "id": "call-1"}],
            ),
            AIMessage(content="Réponse finale basée sur l'outil."),
        ]
    )
    app = build_graph(llm, [echo_tool], MemorySaver())

    result = await app.ainvoke(
        {"messages": [("user", "dis bonjour")]},
        config={"configurable": {"thread_id": "test-1"}},
    )

    assert echo_tool.calls == [{"text": "bonjour"}]
    assert result["messages"][-1].content == "Réponse finale basée sur l'outil."


async def test_agent_answers_directly_without_tool_call(echo_tool: EchoTool):
    llm = ScriptedChatModel(responses=[AIMessage(content="Pas besoin d'outil ici.")])
    app = build_graph(llm, [echo_tool], MemorySaver())

    result = await app.ainvoke(
        {"messages": [("user", "bonjour")]},
        config={"configurable": {"thread_id": "test-2"}},
    )

    assert echo_tool.calls == []
    assert result["messages"][-1].content == "Pas besoin d'outil ici."


async def test_agent_remembers_history_across_turns(echo_tool: EchoTool):
    llm = ScriptedChatModel(
        responses=[AIMessage(content="première réponse"), AIMessage(content="deuxième réponse")]
    )
    app = build_graph(llm, [echo_tool], MemorySaver())
    config = {"configurable": {"thread_id": "test-3"}}

    await app.ainvoke({"messages": [("user", "premier message")]}, config=config)
    result = await app.ainvoke({"messages": [("user", "deuxième message")]}, config=config)

    stored_messages = [m.content for m in result["messages"]]
    assert "premier message" in stored_messages
    assert "deuxième réponse" == result["messages"][-1].content


async def test_agent_stops_when_llm_never_stops_calling_tools(echo_tool: EchoTool):
    always_calls_tool = AIMessage(
        content="", tool_calls=[{"name": "echo", "args": {"text": "boucle"}, "id": "call-x"}]
    )
    llm = ScriptedChatModel(responses=[always_calls_tool])
    app = build_graph(llm, [echo_tool], MemorySaver())

    with pytest.raises(GraphRecursionError):
        await app.ainvoke(
            {"messages": [("user", "boucle infinie")]},
            config={"configurable": {"thread_id": "test-4"}, "recursion_limit": 6},
        )
