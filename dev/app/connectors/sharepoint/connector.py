from dataclasses import dataclass

import httpx

from app.connectors.base import Connector
from app.connectors.document.extraction import extract_text
from app.connectors.sharepoint import graph_client
from app.connectors.sharepoint.schemas import SharePointConnectorConfig
from app.core.exceptions import ConnectorConfigError
from app.rag.schemas import DocumentIn

# .xlsx/.pptx/images non gérés pour l'instant — extract_text() (app/connectors/document) ne sait
# extraire du texte que de .pdf/.docx/texte brut ; un fichier hors de cette liste est simplement
# ignoré plutôt que de faire échouer toute la synchronisation.
SUPPORTED_EXTENSIONS = {"pdf", "docx", "txt", "md"}


@dataclass
class SharePointFileItem:
    web_url: str
    name: str
    text: str


class SharePointConnector(Connector):
    """Synchronise récursivement tous les fichiers d'un dossier/bibliothèque SharePoint (Microsoft
    Graph API, authentification application « client credentials ») dans la base de connaissances
    RAG. `site_url` accepte soit l'URL d'un site SharePoint nu, soit — cas d'usage réel le plus
    courant — l'URL copiée depuis le navigateur sur la page AllItems.aspx d'un dossier précis
    (voir `graph_client.parse_sharepoint_url`)."""

    name = "sharepoint"
    display_name = "SharePoint (dossier)"
    description = (
        "Synchronise récursivement tous les documents (PDF, Word, texte) d'un dossier ou d'une "
        "bibliothèque SharePoint, via Microsoft Graph API."
    )
    config_schema = SharePointConnectorConfig

    async def fetch_items(
        self,
        *,
        site_url: str,
        library_name: str | None = None,
        folder_path: str | None = None,
        credential_alias: str = "default",
    ) -> list[SharePointFileItem]:
        location = graph_client.parse_sharepoint_url(site_url)
        if library_name:
            location.library_name = library_name
        if folder_path is not None:
            location.folder_path = folder_path

        token = await graph_client.get_access_token(credential_alias)
        async with httpx.AsyncClient(
            base_url=graph_client.GRAPH_BASE_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        ) as client:
            drive_id = await graph_client.resolve_drive_id(
                client, location.hostname, location.site_path, location.library_name
            )
            files = await graph_client.list_files_recursive(client, drive_id, location.folder_path)

            items: list[SharePointFileItem] = []
            for file in files:
                suffix = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
                if suffix not in SUPPORTED_EXTENSIONS:
                    continue
                raw_bytes = await graph_client.download_file(client, file.download_url)
                try:
                    text = extract_text(filename=file.name, raw_bytes=raw_bytes)
                except ConnectorConfigError:
                    continue  # fichier illisible (scanné, corrompu, ...) : ignoré, pas bloquant
                items.append(SharePointFileItem(web_url=file.web_url, name=file.name, text=text))
            return items

    def to_document(self, item: SharePointFileItem) -> DocumentIn:
        return DocumentIn(
            source=f"sharepoint:{item.web_url}", content=f"{item.name}\n\n{item.text}"
        )
