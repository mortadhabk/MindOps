import httpx
from pydantic import BaseModel, Field

from app.agent.tools.base import Tool
from app.config import get_settings

MAILTRAP_SANDBOX_URL = "https://sandbox.api.mailtrap.io/api/send"


class SendEmailArgs(BaseModel):
    to: str = Field(description="Adresse email du destinataire")
    subject: str = Field(description="Objet de l'email")
    body: str = Field(description="Corps du message, texte brut")


class SendEmailTool(Tool):
    """Outil sensible (US-404) : la politique de confiance et la création de l'ActionProposal
    sont gérées par le nœud `call_tools` de l'orchestrateur (voir `agent/orchestrator.py`),
    jamais ici — `execute()` ne fait que l'envoi réel, une fois le feu vert obtenu.

    Fournisseur branché : sandbox Mailtrap (e-mails capturés dans une boîte fictive, jamais
    réellement délivrés — idéal pour tester le pattern complet sans risque). Remplaçable par
    Resend/SendGrid en changeant uniquement cette méthode, sans toucher au reste du système.
    """

    name = "send_email"
    description = (
        "Envoie un email récapitulatif à un destinataire. Nécessite potentiellement une "
        "validation humaine selon la politique de confiance configurée pour ce type d'action."
    )
    args_schema = SendEmailArgs
    sensitive = True

    async def execute(self, *, to: str, subject: str, body: str) -> str:
        settings = get_settings()
        if settings.email_api_key is None or settings.mailtrap_inbox_id is None:
            return (
                "échec : EMAIL_API_KEY et/ou MAILTRAP_INBOX_ID non configurées "
                f"(destinataire prévu : {to})"
            )

        payload = {
            "from": {"email": settings.email_from or "agent@ai-agent-poc.local", "name": "Agent"},
            "to": [{"email": to}],
            "subject": subject,
            "text": body,
        }
        headers = {"Authorization": f"Bearer {settings.email_api_key}"}
        url = f"{MAILTRAP_SANDBOX_URL}/{settings.mailtrap_inbox_id}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            return f"échec : impossible de joindre Mailtrap ({exc})"

        if response.status_code >= 400:
            return f"échec : Mailtrap a renvoyé {response.status_code} ({response.text[:200]})"
        inbox = settings.mailtrap_inbox_id
        return f"envoyé à {to} (capturé dans la sandbox Mailtrap, inbox {inbox})"
