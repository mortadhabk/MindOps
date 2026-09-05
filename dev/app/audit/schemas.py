from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(examples=[1])
    event_type: str = Field(examples=["gating.decision"])
    source: str = Field(examples=["gating"])
    payload: dict = Field(examples=[{"proposal_id": 1, "decision": "approve"}])
    result: str | None = Field(default=None)
    created_at: datetime
