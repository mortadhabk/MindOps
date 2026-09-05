from langgraph.types import Command

from app.agent.llm_client import get_llm_client
from app.agent.memory import checkpointer
from app.agent.orchestrator import RECURSION_LIMIT, build_graph
from app.agent.tools.search_knowledge import SearchKnowledgeTool
from app.agent.tools.send_email import SendEmailTool
from app.core.database import async_session_factory
from app.gating.models import ActionProposal, ActionStatus
from app.rag.embeddings import get_embedding_provider


async def resume_agent_graph(proposal_id: int) -> None:
    """Reprend le graphe LangGraph interrompu pour l'ActionProposal donnée (US-405).

    Adaptateur concret du port `gating.router.GraphResumer` : le seul endroit où l'implémentation
    réelle du module `agent` est branchée derrière l'interface exposée par `gating`, via un
    override câblé dans `main.py` (composition root) — `gating` n'importe jamais `agent`,
    conformément à la règle de dépendance du projet.
    """
    async with async_session_factory() as db:
        proposal = await db.get(ActionProposal, proposal_id)
        if proposal is None:
            return

        provider = get_embedding_provider()
        llm = get_llm_client()
        tools = [SearchKnowledgeTool(db=db, provider=provider), SendEmailTool()]
        graph = build_graph(llm, tools, checkpointer, db)
        config = {
            "configurable": {"thread_id": proposal.conversation_id},
            "recursion_limit": RECURSION_LIMIT,
        }
        # La valeur passée à resume n'est pas relue par _run_sensitive_tool, qui redérive la
        # décision depuis la base (proposal.status) après db.refresh() — seule compte ici la
        # reprise elle-même, qui débloque l'appel à interrupt() resté en attente.
        approved = proposal.status == ActionStatus.APPROVED
        await graph.ainvoke(Command(resume={"approved": approved}), config=config)
