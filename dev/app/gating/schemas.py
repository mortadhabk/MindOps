from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.gating.models import ActionStatus


class ActionProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(examples=[1])
    action_type: str = Field(examples=["send_email"])
    parameters: dict = Field(examples=[{"to": "client@example.com", "subject": "Suivi"}])
    status: ActionStatus
    conversation_id: str = Field(examples=["conv-1"])
    result: str | None = Field(default=None)
    created_at: datetime
    decided_at: datetime | None = Field(default=None)
    executed_at: datetime | None = Field(default=None)


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$", examples=["approve"])
