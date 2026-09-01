from pydantic import BaseModel, Field


class DocumentIn(BaseModel):
    source: str = Field(min_length=1)
    content: str = Field(min_length=1)


class IngestResponse(BaseModel):
    document_id: int
    status: str
    chunks_created: int


class SearchResultItem(BaseModel):
    chunk_id: int
    document_id: int
    text: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
