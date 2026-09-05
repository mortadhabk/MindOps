from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SyncResponse(BaseModel):
    connector: str = Field(examples=["github"])
    synced: int = Field(examples=[12])
    errors: list[str] = Field(default_factory=list)


class ConnectorTypeOut(BaseModel):
    name: str = Field(examples=["github"])
    display_name: str = Field(examples=["GitHub Issues"])
    description: str
    config_schema: dict = Field(description="JSON Schema des paramètres attendus par ce type")


class ConnectorInstanceCreate(BaseModel):
    connector_type: str = Field(examples=["github"])
    display_name: str = Field(min_length=1, examples=["Repo backend"])
    config: dict = Field(default_factory=dict)
    position_x: float = 0
    position_y: float = 0


class ConnectorInstancePositionUpdate(BaseModel):
    position_x: float
    position_y: float


class ConnectorInstanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(examples=[1])
    connector_type: str = Field(examples=["github"])
    display_name: str = Field(examples=["Repo backend"])
    config: dict
    position_x: float
    position_y: float
    status: str = Field(examples=["idle"])
    last_synced_at: datetime | None = Field(default=None)
    last_result: dict | None = Field(default=None, examples=[{"synced": 12, "errors": []}])
    created_at: datetime
