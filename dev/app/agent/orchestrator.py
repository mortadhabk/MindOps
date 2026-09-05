from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import Tool
from app.gating import policy
from app.gating.models import ActionStatus
from app.gating.queue_service import create_proposal, get_proposal_for_tool_call

SYSTEM_PROMPT = (
    "Tu es un assistant qui répond aux questions en t'appuyant sur la base de connaissances "
    "via l'outil search_knowledge quand c'est pertinent. Cite les sources utilisées. "
    "Avant de rédiger le contenu d'une action comme l'envoi d'un email, recherche toujours "
    "d'abord les faits pertinents via search_knowledge — ne compose jamais un contenu à "
    "partir d'informations que tu n'as pas vérifiées, et ne laisse jamais de placeholder "
    "(comme [cause racine]) non rempli."
)

# Une itération = un aller-retour (appel LLM + éventuel appel outil). Le recursion_limit
# de LangGraph compte chaque étape du graphe, donc on double pour couvrir call_model + tools.
MAX_ITERATIONS = 5
RECURSION_LIMIT = MAX_ITERATIONS * 2


def build_graph(
    llm: BaseChatModel,
    tools: Sequence[Tool],
    checkpointer: BaseCheckpointSaver,
    db: AsyncSession,
):
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

    async def call_tools(state: MessagesState, config: RunnableConfig) -> dict:
        last_message = state["messages"][-1]
        conversation_id = config["configurable"]["thread_id"]
        results = []
        for call in last_message.tool_calls:
            tool = tools_by_name.get(call["name"])
            if tool is None:
                content = f"Outil inconnu : {call['name']}"
            elif not tool.sensitive:
                content = await tool.execute(**call["args"])  # inchangé — chemin Epic 3
            else:
                content = await _run_sensitive_tool(db, tool, call, conversation_id)
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


async def _run_sensitive_tool(
    db: AsyncSession, tool: Tool, call: dict, conversation_id: str
) -> str:
    """Politique de confiance appliquée à un outil sensible (Epic 4, US-402 à US-405).

    Idempotent par construction : ce nœud est rejoué depuis son début à chaque reprise après
    interrupt() (voir module 02 du manuel de gating), donc toute création de proposition passe
    d'abord par une recherche sur `tool_call_id` avant d'en créer une nouvelle.
    """
    existing = await get_proposal_for_tool_call(db, call["id"])
    if existing is not None and existing.status == ActionStatus.EXECUTED:
        return existing.result or ""

    decision = policy.evaluate(tool.name, confidence=1.0)
    if decision is policy.Decision.SUGGEST_ONLY:
        return f"Suggestion : {tool.name}({call['args']}) — non exécutée (suggest_only)."

    if existing is None:
        status = (
            ActionStatus.APPROVED
            if decision is policy.Decision.AUTO_EXECUTE
            else ActionStatus.PENDING
        )
        proposal = await create_proposal(
            db,
            tool_call_id=call["id"],
            conversation_id=conversation_id,
            action_type=tool.name,
            parameters=call["args"],
            status=status,
        )
    else:
        proposal = existing

    if proposal.status == ActionStatus.PENDING:
        # ★ pause ici — le graphe s'arrête, l'état est persisté par le checkpointer, et la main
        # revient à l'appelant. La reprise se fait via POST /gating/{id}/decide, qui invoque
        # Command(resume=...) (voir agent/resume_service.py).
        interrupt(
            {"proposal_id": proposal.id, "action_type": tool.name, "parameters": call["args"]}
        )
        # gating.queue_service.decide() a déjà mis à jour le statut en base avant la reprise.
        await db.refresh(proposal)

    # Attention : à la reprise, proposal.status n'est plus PENDING (decide() l'a déjà changé),
    # donc cette vérification doit rester HORS du bloc ci-dessus, pas à l'intérieur — sinon un
    # rejet serait silencieusement ignoré et l'outil s'exécuterait quand même (bug corrigé grâce
    # à test_agent_resume_after_rejection_never_executes).
    if proposal.status != ActionStatus.APPROVED:
        return f"Action rejetée par le validateur (proposition #{proposal.id})."

    result = await tool.execute(**call["args"])
    proposal.status = ActionStatus.EXECUTED
    proposal.result = result
    # .replace(tzinfo=None) : colonne TIMESTAMP WITHOUT TIME ZONE (voir queue_service.decide)
    proposal.executed_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    return result


async def stream_chat(app, *, conversation_id: str, user_message: str) -> AsyncIterator[str]:
    config = {"configurable": {"thread_id": conversation_id}, "recursion_limit": RECURSION_LIMIT}
    inputs = {"messages": [HumanMessage(content=user_message)]}
    try:
        async for chunk, metadata in app.astream(inputs, config=config, stream_mode="messages"):
            if metadata.get("langgraph_node") == "call_model" and chunk.content:
                yield chunk.content
    except GraphRecursionError:
        yield "\n\n[Erreur : nombre maximum d'itérations atteint sans réponse finale.]"
