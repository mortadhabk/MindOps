from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.models import Conversation

TITLE_MAX_LENGTH = 80


def _make_title(message: str) -> str:
    text = " ".join(message.split())
    if len(text) <= TITLE_MAX_LENGTH:
        return text
    return text[: TITLE_MAX_LENGTH - 1].rstrip() + "…"


async def touch_conversation(db: AsyncSession, conversation_id: str, first_message: str) -> None:
    """Crée la conversation au premier message (titre dérivé de ce message, jamais changé
    ensuite pour rester stable dans la sidebar), sinon se contente de rafraîchir `updated_at`
    pour que le tri par activité récente reste correct."""
    now = datetime.now(UTC).replace(tzinfo=None)
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        db.add(
            Conversation(
                id=conversation_id, title=_make_title(first_message), created_at=now, updated_at=now
            )
        )
    else:
        conversation.updated_at = now
    await db.commit()
