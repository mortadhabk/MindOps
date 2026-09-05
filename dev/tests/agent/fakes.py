from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel, PrivateAttr

from app.agent.tools.base import Tool


class ScriptedChatModel(BaseChatModel):
    """LLM factice qui rejoue une liste de réponses prédéfinies, un appel à la fois."""

    responses: list[AIMessage]
    _call_count: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        index = min(self._call_count, len(self.responses) - 1)
        self._call_count += 1
        # Nouvel id a chaque appel : le reducer `add_messages` de LangGraph fusionne par id,
        # donc rejouer le meme objet ecraserait le message precedent au lieu d'en ajouter un.
        template = self.responses[index]
        message = AIMessage(content=template.content, tool_calls=template.tool_calls)
        return ChatResult(generations=[ChatGeneration(message=message)])


class EchoArgs(BaseModel):
    text: str


class EchoTool(Tool):
    """Outil factice pour tester la boucle agentique sans dépendre du RAG/DB."""

    name = "echo"
    description = "Renvoie le texte reçu, préfixé, pour vérifier que l'outil a été appelé."
    args_schema = EchoArgs

    def __init__(self):
        self.calls: list[dict] = []

    async def execute(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return f"echo: {kwargs.get('text', '')}"


class FakeSensitiveArgs(BaseModel):
    value: str


class FakeSensitiveTool(Tool):
    """Outil sensible factice (Epic 4) : mêmes garanties que SendEmailTool, sans réseau —
    permet de tester le cycle policy/interrupt/resume sans dépendance externe."""

    name = "fake_sensitive_action"
    description = "Outil de test, sensible, pour vérifier le cycle gating sans dépendance externe."
    args_schema = FakeSensitiveArgs
    sensitive = True

    def __init__(self):
        self.delivered: list[str] = []

    async def execute(self, *, value: str) -> str:
        self.delivered.append(value)
        return f"livré: {value}"
