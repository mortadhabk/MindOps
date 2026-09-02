from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(default=None, examples=["conv-1"])
    message: str = Field(min_length=1, examples=["Pourquoi le paiement échoue ?"])
