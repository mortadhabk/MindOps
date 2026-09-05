from app.connectors.base import Connector
from app.connectors.document.schemas import DocumentConnectorConfig
from app.rag.schemas import DocumentIn


class DocumentConnector(Connector):
    """Cas particulier du Studio (Epic 8, US 8.4) : pas de source externe à interroger, le texte
    est collé ou un fichier texte est déposé directement dans le formulaire de configuration —
    `fetch_items()` renvoie l'unique item porté par la config elle-même. Resynchroniser ré-ingère
    ce même contenu (upsert par `source`, voir `rag.ingestion.ingest_document`) : inoffensif si
    rien n'a changé, utile si le document a été remplacé en supprimant/recréant l'instance.
    """

    name = "document"
    display_name = "Document"
    description = "Texte collé ou fichier texte déposé directement, sans connecteur externe."
    config_schema = DocumentConnectorConfig

    async def fetch_items(self, *, source: str, content: str) -> list[dict[str, str]]:
        return [{"source": source, "content": content}]

    def to_document(self, item: dict[str, str]) -> DocumentIn:
        return DocumentIn(source=item["source"], content=item["content"])
