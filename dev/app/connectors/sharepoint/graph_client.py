import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.connectors.credential_settings import get_sharepoint_credentials
from app.core.exceptions import ConnectorConfigError, ConnectorError

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
PAGE_SIZE = 200

# Cache mémoire du jeton d'accès (client credentials), par alias — évite une authentification à
# chaque fichier listé/téléchargé. Un jeton Graph app-only vit ~1h ; on le renouvelle 60s avant
# expiration, avec une marge suffisante pour couvrir la durée d'une synchronisation en cours.
_token_cache: dict[str, tuple[str, float]] = {}


@dataclass
class SharePointLocation:
    hostname: str
    site_path: str  # ex : "/sites/ENACWebFactory-TMAPowerPlatform"
    library_name: str  # ex : "Documents partagés"
    folder_path: str = ""  # ex : "General/Documentations/Portail ENIX" ("" = racine bibliothèque)


@dataclass
class SharePointFile:
    id: str
    name: str
    web_url: str
    download_url: str
    folder_path: str = field(default="")


def parse_sharepoint_url(url: str) -> SharePointLocation:
    """Découpe l'URL copiée depuis le navigateur en (site, bibliothèque, dossier) exploitables
    par Graph API. Deux formes acceptées :

    - la page d'un dossier précis :
      `https://{tenant}.sharepoint.com/sites/{site}/{library}/Forms/AllItems.aspx?id=%2Fsites%2F...`
      — le paramètre `id` (encodé) porte le chemin serveur complet jusqu'au dossier ciblé ;
    - une URL de site nue : `https://{tenant}.sharepoint.com/sites/{site}` — toute la bibliothèque
      par défaut ("Documents partagés"/"Shared Documents") sera alors synchronisée depuis sa racine.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if not hostname.endswith(".sharepoint.com"):
        raise ConnectorConfigError(f"URL SharePoint invalide (hôte inattendu) : {url}")

    query = parse_qs(parsed.query)
    raw_id = query.get("id", [None])[0]
    server_relative_path = unquote(raw_id) if raw_id else unquote(parsed.path)

    segments = [s for s in server_relative_path.split("/") if s]
    if len(segments) < 2 or segments[0] != "sites":
        raise ConnectorConfigError(
            f"Impossible d'identifier le site SharePoint dans cette URL : {url}"
        )

    site_path = f"/sites/{segments[1]}"
    if len(segments) < 3:
        # URL de site nue, sans bibliothèque explicite — valeur par défaut la plus courante côté
        # tenant francophone ; l'appelant peut toujours la surcharger via `library_name`.
        return SharePointLocation(
            hostname=hostname, site_path=site_path, library_name="Documents partagés"
        )

    library_name = segments[2]
    folder_path = "/".join(segments[3:])
    return SharePointLocation(
        hostname=hostname, site_path=site_path, library_name=library_name, folder_path=folder_path
    )


async def get_access_token(credential_alias: str) -> str:
    cached = _token_cache.get(credential_alias)
    if cached and cached[1] > time.monotonic() + 60:
        return cached[0]

    creds = get_sharepoint_credentials(credential_alias)
    if creds is None:
        raise ConnectorConfigError(
            f"Aucun identifiant SharePoint configuré pour l'alias « {credential_alias} » (à "
            "saisir dans Paramètres > Connecteurs — identifiants, ou SHAREPOINT_TENANT_ID / "
            "SHAREPOINT_CLIENT_ID / SHAREPOINT_CLIENT_SECRET dans .env)"
        )

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            TOKEN_URL_TEMPLATE.format(tenant_id=creds.tenant_id),
            data={
                "grant_type": "client_credentials",
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scope": "https://graph.microsoft.com/.default",
            },
        )
    if response.is_error:
        raise ConnectorError(
            "Authentification SharePoint (Azure AD) échouée", details={"body": response.text}
        )
    payload = response.json()
    token = payload["access_token"]
    _token_cache[credential_alias] = (token, time.monotonic() + payload.get("expires_in", 3600))
    return token


async def resolve_drive_id(
    client: httpx.AsyncClient, hostname: str, site_path: str, library_name: str
) -> str:
    """Renvoie le drive_id de la bibliothèque documentaire nommée `library_name`."""
    site_response = await client.get(f"/sites/{hostname}:{site_path}")
    if site_response.is_error:
        raise ConnectorError(
            f"Site SharePoint introuvable : {hostname}{site_path}",
            details={"body": site_response.text},
        )
    site_id = site_response.json()["id"]

    drives_response = await client.get(f"/sites/{site_id}/drives")
    if drives_response.is_error:
        raise ConnectorError(
            "Impossible de lister les bibliothèques du site",
            details={"body": drives_response.text},
        )
    drives = drives_response.json().get("value", [])
    for drive in drives:
        if drive["name"].lower() == library_name.lower():
            return drive["id"]

    available = [d["name"] for d in drives]
    raise ConnectorConfigError(
        f"Bibliothèque « {library_name} » introuvable sur ce site (disponibles : {available})"
    )


async def list_files_recursive(
    client: httpx.AsyncClient, drive_id: str, folder_path: str
) -> list[SharePointFile]:
    """Parcourt récursivement `folder_path` (et tous ses sous-dossiers) et renvoie tous les
    fichiers rencontrés — les dossiers eux-mêmes ne sont jamais renvoyés dans le résultat."""
    files: list[SharePointFile] = []
    await _walk_folder(client, drive_id, folder_path, files)
    return files


async def _walk_folder(
    client: httpx.AsyncClient, drive_id: str, folder_path: str, out: list[SharePointFile]
) -> None:
    anchor = f"root:/{folder_path}:" if folder_path else "root"
    url: str | None = f"/drives/{drive_id}/{anchor}/children?$top={PAGE_SIZE}"

    while url:
        response = await client.get(url)
        if response.is_error:
            raise ConnectorError(
                f"Impossible de lister le dossier « {folder_path or '/'} »",
                details={"body": response.text},
            )
        payload = response.json()
        for item in payload.get("value", []):
            if "folder" in item:
                child_path = f"{folder_path}/{item['name']}" if folder_path else item["name"]
                await _walk_folder(client, drive_id, child_path, out)
            elif "file" in item:
                download_url = item.get("@microsoft.graph.downloadUrl")
                if download_url:
                    out.append(
                        SharePointFile(
                            id=item["id"],
                            name=item["name"],
                            web_url=item["webUrl"],
                            download_url=download_url,
                            folder_path=folder_path,
                        )
                    )
        # @odata.nextLink est une URL absolue (host Graph inclus) — httpx.AsyncClient.get()
        # l'accepte telle quelle même avec un base_url configuré (elle n'est pas résolue contre
        # celui-ci), donc pas besoin de la retraiter.
        url = payload.get("@odata.nextLink")


async def download_file(client: httpx.AsyncClient, download_url: str) -> bytes:
    response = await client.get(download_url)
    if response.is_error:
        raise ConnectorError(
            f"Téléchargement échoué : {download_url}", details={"body": response.text}
        )
    return response.content
