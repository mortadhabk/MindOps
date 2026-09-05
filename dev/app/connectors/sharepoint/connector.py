from dataclasses import dataclass

from app.connectors.base import Connector
from app.connectors.sharepoint.schemas import SharePointConnectorConfig
from app.rag.schemas import DocumentIn

FIXED_ITEMS: list[dict[str, str | int]] = [
    {
        "id": 1,
        "title": "Procédure de remboursement fournisseur",
        "text": (
            "Tout remboursement fournisseur superieur a 5000 euros necessite une double "
            "validation : le responsable achats, puis la direction financiere, avant tout "
            "virement. En dessous de ce seuil, la validation du responsable achats suffit."
        ),
    },
    {
        "id": 2,
        "title": "Politique de télétravail",
        "text": (
            "Les collaborateurs peuvent teletravailler jusqu'a 3 jours par semaine, sous reserve "
            "de validation du manager. Le materiel (ecran, clavier) est fourni sur demande via "
            "le portail RH, dans la limite d'un equipement par collaborateur."
        ),
    },
]


@dataclass
class SharePointListItem:
    site_url: str
    library_name: str
    id: int
    title: str
    text: str


class SharePointConnector(Connector):
    """Adapter *factice* pour l'instant (Epic 8, décision actée : pas de tenant Azure AD de test
    disponible — voir management/epic-8-studio-connecteurs.md, section 4.3).

    Expose le même `config_schema` et le même contrat `Connector` que la future implémentation
    Microsoft Graph API (client credentials, permission `Sites.Selected`) : le jour où un tenant
    réel est disponible, seuls `fetch_items()`/`to_document()` changeront — ni le Studio, ni les
    endpoints `/connectors/*`, ni le formulaire de configuration n'auront à évoluer. C'est
    précisément ce que cette Epic doit démontrer : l'abstraction généralise au-delà de GitHub.
    """

    name = "sharepoint"
    display_name = "SharePoint (liste)"
    description = (
        "Synchronise une liste SharePoint comme base de connaissances. Connecteur factice pour "
        "l'instant (aucun tenant Azure AD de test disponible) : renvoie toujours les mêmes items."
    )
    config_schema = SharePointConnectorConfig

    async def fetch_items(
        self,
        *,
        site_url: str,
        library_name: str = "Documents partagés",
        credential_alias: str = "default",
    ) -> list[SharePointListItem]:
        return [
            SharePointListItem(site_url=site_url, library_name=library_name, **item)
            for item in FIXED_ITEMS
        ]

    def to_document(self, item: SharePointListItem) -> DocumentIn:
        return DocumentIn(
            source=f"sharepoint:{item.site_url}/{item.library_name}#{item.id}",
            content=f"{item.title}\n\n{item.text}",
        )
