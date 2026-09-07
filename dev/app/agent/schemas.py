from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(default=None, examples=["conv-1"])
    message: str = Field(min_length=1, examples=["Pourquoi le paiement échoue ?"])


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationMessageOut(BaseModel):
    role: str = Field(examples=["user", "assistant"])
    text: str
