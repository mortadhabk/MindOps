from collections.abc import AsyncIterator, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, MessagesState, StateGraph

from app.agent.tools.base import Tool

SYSTEM_PROMPT = (
    "Tu es un assistant qui répond aux questions en t'appuyant sur la base de connaissances "
    "via l'outil search_knowledge quand c'est pertinent. Cite les sources utilisées."
)

# Une itération = un aller-retour (appel LLM + éventuel appel outil). Le recursion_limit
# de LangGraph compte chaque étape du graphe, donc on double pour couvrir call_model + tools.
MAX_ITERATIONS = 5
RECURSION_LIMIT = MAX_ITERATIONS * 2


def build_graph(llm: BaseChatModel, tools: Sequence[Tool], checkpointer: BaseCheckpointSaver):
    tools_by_name = {tool.name: tool for tool in tools}
    tool_defs = [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.args_schema.model_json_schema(),
        }
        for tool in tools
    ]
    llm_with_tools = llm.bind_tools(tool_defs) if tool_defs else llm

    async def call_model(state: MessagesState) -> dict:
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    async def call_tools(state: MessagesState) -> dict:
        last_message = state["messages"][-1]
        results = []
        for call in last_message.tool_calls:
            tool = tools_by_name.get(call["name"])
            if tool is None:
                content = f"Outil inconnu : {call['name']}"
            else:
                content = await tool.execute(**call["args"])
            results.append(ToolMessage(content=content, tool_call_id=call["id"]))
        return {"messages": results}

    def route_after_model(state: MessagesState) -> str:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("call_model", call_model)
    graph.add_node("tools", call_tools)
    graph.set_entry_point("call_model")
    graph.add_conditional_edges("call_model", route_after_model, {"tools": "tools", END: END})
    graph.add_edge("tools", "call_model")

    return graph.compile(checkpointer=checkpointer)


async def stream_chat(app, *, conversation_id: str, user_message: str) -> AsyncIterator[str]:
    config = {"configurable": {"thread_id": conversation_id}, "recursion_limit": RECURSION_LIMIT}
    inputs = {"messages": [HumanMessage(content=user_message)]}
    try:
        async for chunk, metadata in app.astream(inputs, config=config, stream_mode="messages"):
            if metadata.get("langgraph_node") == "call_model" and chunk.content:
                yield chunk.content
    except GraphRecursionError:
        yield "\n\n[Erreur : nombre maximum d'itérations atteint sans réponse finale.]"
