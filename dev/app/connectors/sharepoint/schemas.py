from pydantic import BaseModel, Field


class SharePointConnectorConfig(BaseModel):
    """Paramètres d'une ConnectorInstance de type "sharepoint".

    `credential_alias` ne pointe jamais un secret directement, seulement un alias résolu côté
    serveur (SHAREPOINT_TENANT_ID/CLIENT_ID/CLIENT_SECRET dans `.env`), pour qu'aucun identifiant
    ne transite jamais par le navigateur.
    """

    site_url: str = Field(
        description=(
            "URL du site SharePoint, ou — plus pratique en usage réel — l'URL copiée depuis le "
            "navigateur sur la page d'un dossier précis (.../Forms/AllItems.aspx?id=...)"
        ),
        examples=[
            "https://orange0.sharepoint.com/sites/ENACWebFactory-TMAPowerPlatform/"
            "Documents%20partages/Forms/AllItems.aspx?id=%2Fsites%2FENACWebFactory-TMAPowerPlatform"
            "%2FDocuments%20partages%2FGeneral%2FDocumentations%2FPortail%20ENIX"
        ],
    )
    library_name: str | None = Field(
        default=None,
        description="Bibliothèque à synchroniser — déduite de site_url si absente",
    )
    folder_path: str | None = Field(
        default=None,
        description="Sous-dossier à synchroniser récursivement — déduit de site_url si absent",
    )
    credential_alias: str = Field(
        default="default",
        description="Alias d'identifiants Azure AD pré-configurés côté serveur (jamais saisis ici)",
    )
