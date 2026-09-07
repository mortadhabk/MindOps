import base64
from datetime import datetime

import httpx

from app.connectors.jira.settings import get_jira_cloud_credentials, get_jira_server_token
from app.core.exceptions import ConnectorConfigError, ConnectorError

PAGE_SIZE = 100


def _auth_headers(deployment_type: str, credential_alias: str) -> dict[str, str]:
    if deployment_type == "cloud":
        creds = get_jira_cloud_credentials(credential_alias)
        if creds is None:
            raise ConnectorConfigError(
                f"Aucun identifiant Jira Cloud configuré pour l'alias « {credential_alias} » "
                "(à saisir dans Paramètres > Connecteurs — identifiants, ou JIRA_CLOUD_EMAIL / "
                "JIRA_CLOUD_API_TOKEN dans .env)"
            )
        token = base64.b64encode(f"{creds.email}:{creds.api_token}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    if deployment_type == "server":
        pat = get_jira_server_token(credential_alias)
        if pat is None:
            raise ConnectorConfigError(
                f"Aucun identifiant Jira Server configuré pour l'alias « {credential_alias} » "
                "(à saisir dans Paramètres > Connecteurs — identifiants, ou JIRA_SERVER_TOKEN "
                "dans .env)"
            )
        return {"Authorization": f"Bearer {pat}"}

    raise ConnectorConfigError(
        f"deployment_type inconnu : « {deployment_type} » (attendu : cloud | server)"
    )


def build_client(base_url: str, deployment_type: str, credential_alias: str) -> httpx.AsyncClient:
    headers = _auth_headers(deployment_type, credential_alias)
    headers["Accept"] = "application/json"
    return httpx.AsyncClient(base_url=base_url.rstrip("/"), headers=headers, timeout=30.0)


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code in (401, 403):
        raise ConnectorError("Authentification Jira refusée", details={"body": response.text})
    if response.status_code == 404:
        raise ConnectorConfigError(f"Ressource Jira introuvable : {response.request.url}")
    if response.is_error:
        raise ConnectorError(
            f"Erreur API Jira ({response.status_code})", details={"body": response.text}
        )


async def search_issues(
    client: httpx.AsyncClient,
    *,
    api_version: str,
    project_key: str,
    since: datetime | None,
) -> list[dict]:
    """Recherche paginée (`startAt`/`maxResults`/`total`) — commune aux API v2 (Server/DC) et v3
    (Cloud), triée par date de mise à jour croissante pour qu'une synchronisation interrompue en
    cours de route reprenne sans trou au prochain `since` (voir `instance_service.run_sync`)."""
    jql = f"project = {project_key}"
    if since is not None:
        jql += f' AND updated >= "{since.strftime("%Y-%m-%d %H:%M")}"'
    jql += " ORDER BY updated ASC"

    issues: list[dict] = []
    start_at = 0
    while True:
        response = await client.get(
            f"/rest/api/{api_version}/search",
            params={
                "jql": jql,
                "startAt": start_at,
                "maxResults": PAGE_SIZE,
                "fields": "summary,description,status,issuetype,labels,assignee,attachment",
            },
        )
        _raise_for_status(response)
        payload = response.json()
        page = payload.get("issues", [])
        issues.extend(page)
        start_at += len(page)
        if not page or start_at >= payload.get("total", 0):
            break
    return issues


async def fetch_comments(
    client: httpx.AsyncClient, *, api_version: str, issue_key: str
) -> list[dict]:
    comments: list[dict] = []
    start_at = 0
    while True:
        response = await client.get(
            f"/rest/api/{api_version}/issue/{issue_key}/comment",
            params={"startAt": start_at, "maxResults": PAGE_SIZE},
        )
        _raise_for_status(response)
        payload = response.json()
        page = payload.get("comments", [])
        comments.extend(page)
        start_at += len(page)
        if not page or start_at >= payload.get("total", 0):
            break
    return comments


async def download_attachment(client: httpx.AsyncClient, content_url: str) -> bytes:
    # `content_url` est une URL absolue (fournie telle quelle par l'API Jira dans
    # `attachment[].content`) — httpx.AsyncClient.get() l'accepte sans la résoudre contre
    # `base_url`, comme pour les URLs de téléchargement SharePoint (voir sharepoint/graph_client).
    response = await client.get(content_url)
    _raise_for_status(response)
    return response.content
