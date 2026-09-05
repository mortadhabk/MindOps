from pydantic import BaseModel, Field


class DocumentConnectorConfig(BaseModel):
    """Paramètres d'une ConnectorInstance de type "document" (Epic 8, US 8.4).

    Cas particulier : pas de source externe à interroger, le contenu est saisi ou déposé
    directement dans le Studio — la config *est* le document à ingérer.
    """

    source: str = Field(
        min_length=1, description="Identifiant unique du document", examples=["note-support-1"]
    )
    content: str = Field(
        min_length=1, description="Contenu texte à ingérer dans la base de connaissances"
    )


class DocumentExtractionResult(BaseModel):
    text: str = Field(description="Texte extrait du fichier déposé")
    suggested_source: str = Field(description="Nom de fichier sans extension, comme suggestion")
