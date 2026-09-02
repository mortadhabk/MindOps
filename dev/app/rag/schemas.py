from pydantic import BaseModel, Field


class DocumentIn(BaseModel):
    source: str = Field(min_length=1, examples=["manuel"])
    content: str = Field(
        min_length=1,
        examples=[
            "Le service de paiement echoue quand le montant depasse 10 000 euros. "
            "La cause identifiee est un depassement du champ DECIMAL en base de donnees."
        ],
    )


class IngestResponse(BaseModel):
    document_id: int = Field(examples=[1])
    status: str = Field(examples=["complete"])
    chunks_created: int = Field(examples=[1])


class SearchResultItem(BaseModel):
    chunk_id: int = Field(examples=[1])
    document_id: int = Field(examples=[1])
    text: str = Field(
        examples=["Le service de paiement echoue quand le montant depasse 10 000 euros."]
    )
    score: float = Field(examples=[0.78])


class SearchResponse(BaseModel):
    query: str = Field(examples=["pourquoi le paiement ne fonctionne pas au-dela de 10000 euros"])
    results: list[SearchResultItem]
