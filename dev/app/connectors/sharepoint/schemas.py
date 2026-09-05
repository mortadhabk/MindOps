from pydantic import BaseModel, Field


class SharePointConnectorConfig(BaseModel):
    """Paramètres d'une ConnectorInstance de type "sharepoint" (Epic 8).

    Volontairement identique à ce qu'exigera la future implémentation Microsoft Graph API —
    seul `credential_alias` fait exception aux valeurs "normales" : il ne pointe jamais un
    secret directement, seulement un alias résolu côté serveur (`SHAREPOINT_CREDENTIALS` dans
    `.env`), pour qu'aucun identifiant ne transite jamais par le navigateur.
    """

    site_url: str = Field(
        description="URL du site SharePoint",
        examples=["https://monentreprise.sharepoint.com/sites/support"],
    )
    library_name: str = Field(
        default="Documents partagés", description="Liste ou bibliothèque à synchroniser"
    )
    credential_alias: str = Field(
        default="default",
        description="Alias d'identifiants pré-configurés côté serveur (jamais saisis ici)",
    )
