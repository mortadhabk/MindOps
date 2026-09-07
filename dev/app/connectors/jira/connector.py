from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from app.connectors.base import Connector
from app.connectors.document.extraction import extract_text
from app.connectors.jira import client as jira_client
from app.connectors.jira.adf import adf_to_text
from app.connectors.jira.schemas import JiraConnectorConfig
from app.core.exceptions import ConnectorConfigError
from app.rag.schemas import DocumentIn

# .xlsx/images non gérés pour l'instant (OCR en V2, voir management/epic-10-connecteur-jira.md) —
# une pièce jointe hors de cette liste est listée par son nom (traçabilité) plutôt que d'ignorer
# silencieusement son existence ou de faire échouer toute la synchronisation.
SUPPORTED_ATTACHMENT_EXTENSIONS = {"pdf", "docx", "txt", "md"}


@dataclass
class JiraIssueItem:
    key: str
    web_url: str
    text: str


class JiraConnector(Connector):
    """Synchronise tous les tickets d'un projet Jira (Cloud ou Server/Data Center) — résumé,
    description, commentaires et texte des pièces jointes PDF/Word — comme base de connaissances
    RAG. Un ticket = un document (cohérent avec GitHub Issues et SharePoint) ; la description et
    les commentaires Jira Cloud sont en ADF (arbre JSON), convertis via `adf.py` — Jira Server les
    renvoie déjà en texte, utilisé tel quel."""

    name = "jira"
    display_name = "Jira (tickets)"
    description = (
        "Synchronise tous les tickets d'un projet Jira (Cloud ou Server/Data Center) — résumé, "
        "description, commentaires et pièces jointes PDF/Word — comme base de connaissances."
    )
    config_schema = JiraConnectorConfig
    supports_incremental_sync = True

    async def fetch_items(
        self,
        *,
        base_url: str,
        project_key: str,
        deployment_type: str = "cloud",
        credential_alias: str = "default",
        since: datetime | None = None,
    ) -> list[JiraIssueItem]:
        api_version = "3" if deployment_type == "cloud" else "2"
        async with jira_client.build_client(base_url, deployment_type, credential_alias) as http:
            raw_issues = await jira_client.search_issues(
                http, api_version=api_version, project_key=project_key, since=since
            )
            items: list[JiraIssueItem] = []
            for raw in raw_issues:
                items.append(
                    await self._build_item(
                        http,
                        raw,
                        api_version=api_version,
                        deployment_type=deployment_type,
                        base_url=base_url,
                    )
                )
            return items

    async def _build_item(
        self,
        http: httpx.AsyncClient,
        raw: dict,
        *,
        api_version: str,
        deployment_type: str,
        base_url: str,
    ) -> JiraIssueItem:
        fields = raw["fields"]
        key = raw["key"]

        summary = fields.get("summary", "")
        description = self._render_field(fields.get("description"), deployment_type)
        status = (fields.get("status") or {}).get("name", "")
        issue_type = (fields.get("issuetype") or {}).get("name", "")
        labels = fields.get("labels") or []
        assignee = (fields.get("assignee") or {}).get("displayName")
        reporter = (fields.get("reporter") or {}).get("displayName")
        priority = (fields.get("priority") or {}).get("name")

        raw_comments = await jira_client.fetch_comments(
            http, api_version=api_version, issue_key=key
        )
        comments_text = "\n\n".join(
            self._render_field(comment.get("body"), deployment_type) for comment in raw_comments
        ).strip()

        attachments_text = await self._extract_attachments(http, fields.get("attachment") or [])

        parts = [f"[{key}] {summary}", f"Statut : {status} — Type : {issue_type}"]
        if priority:
            parts.append(f"Priorité : {priority}")
        if labels:
            parts.append(f"Labels : {', '.join(labels)}")
        if reporter:
            parts.append(f"Rapporté par : {reporter}")
        if assignee:
            parts.append(f"Assigné à : {assignee}")
        if description:
            parts.append(f"Description :\n{description}")
        if comments_text:
            parts.append(f"Commentaires :\n{comments_text}")
        if attachments_text:
            parts.append(f"Pièces jointes :\n{attachments_text}")

        return JiraIssueItem(
            key=key,
            web_url=f"{base_url.rstrip('/')}/browse/{key}",
            text="\n\n".join(parts),
        )

    def _render_field(self, value: Any, deployment_type: str) -> str:
        if not value:
            return ""
        if deployment_type == "cloud" and isinstance(value, dict):
            return adf_to_text(value)
        return str(value)

    async def _extract_attachments(
        self, http: httpx.AsyncClient, attachments: list[dict]
    ) -> str:
        parts: list[str] = []
        for attachment in attachments:
            filename = attachment.get("filename", "fichier")
            suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if suffix not in SUPPORTED_ATTACHMENT_EXTENSIONS:
                parts.append(f"- {filename} (non traité, format non pris en charge)")
                continue

            content_url = attachment.get("content")
            if not content_url:
                continue
            raw_bytes = await jira_client.download_attachment(http, content_url)
            try:
                text = extract_text(filename=filename, raw_bytes=raw_bytes)
            except ConnectorConfigError:
                parts.append(f"- {filename} (illisible)")
                continue
            parts.append(f"--- {filename} ---\n{text}")
        return "\n\n".join(parts)

    def to_document(self, item: JiraIssueItem) -> DocumentIn:
        return DocumentIn(source=f"jira:{item.web_url}", content=item.text)
