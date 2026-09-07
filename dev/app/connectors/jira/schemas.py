from typing import Literal

from pydantic import BaseModel, Field


class JiraConnectorConfig(BaseModel):
    """Paramètres d'une ConnectorInstance de type "jira" (Epic 10).

    `credential_alias` ne pointe jamais un secret directement, seulement un alias résolu côté
    serveur (JIRA_CLOUD_EMAIL/API_TOKEN ou JIRA_SERVER_TOKEN selon `deployment_type`, voir
    `.env`), pour qu'aucun identifiant ne transite jamais par le navigateur.
    """

    base_url: str = Field(
        description="URL de l'instance Jira",
        examples=["https://monentreprise.atlassian.net"],
    )
    deployment_type: Literal["cloud", "server"] = Field(
        default="cloud",
        description="cloud = *.atlassian.net (API v3) ; server = Jira Server/Data Center (API v2)",
    )
    project_key: str = Field(description="Clé du projet à synchroniser", examples=["SUPPORT"])
    credential_alias: str = Field(
        default="default",
        description="Alias d'identifiants Jira pré-configurés côté serveur (jamais saisis ici)",
    )
