from pydantic import BaseModel, Field


class SyncResponse(BaseModel):
    connector: str = Field(examples=["github"])
    synced: int = Field(examples=[12])
    errors: list[str] = Field(default_factory=list)
