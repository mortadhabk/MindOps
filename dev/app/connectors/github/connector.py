from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.connectors.base import Connector
from app.connectors.github.schemas import GitHubIssue
from app.core.exceptions import ConnectorError
from app.rag.schemas import DocumentIn

API_BASE_URL = "https://api.github.com"
PER_PAGE = 100
MAX_COMMENTS_PER_ISSUE = 20


@dataclass
class GitHubIssueItem:
    owner: str
    repo: str
    issue: GitHubIssue
    comments: list[str]


class GitHubConnector(Connector):
    """Adapter en lecture seule pour l'API GitHub Issues."""

    name = "github"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = get_settings().github_token
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def fetch_items(
        self, *, owner: str, repo: str, state: str = "all", max_pages: int = 10
    ) -> list[GitHubIssueItem]:
        async with httpx.AsyncClient(
            base_url=API_BASE_URL, headers=self._headers(), timeout=10.0
        ) as client:
            issues = await self._fetch_issues(client, owner, repo, state, max_pages)
            items: list[GitHubIssueItem] = []
            for issue in issues:
                comments = await self._fetch_comments(client, owner, repo, issue)
                items.append(
                    GitHubIssueItem(owner=owner, repo=repo, issue=issue, comments=comments)
                )
            return items

    async def _fetch_issues(
        self, client: httpx.AsyncClient, owner: str, repo: str, state: str, max_pages: int
    ) -> list[GitHubIssue]:
        issues: list[GitHubIssue] = []
        for page in range(1, max_pages + 1):
            response = await client.get(
                f"/repos/{owner}/{repo}/issues",
                params={"state": state, "per_page": PER_PAGE, "page": page},
            )
            self._raise_for_status(response, owner, repo)
            page_items = response.json()
            if not page_items:
                break
            for raw in page_items:
                parsed = GitHubIssue.model_validate(raw)
                if not parsed.is_pull_request:
                    issues.append(parsed)
            if len(page_items) < PER_PAGE:
                break
        return issues

    async def _fetch_comments(
        self, client: httpx.AsyncClient, owner: str, repo: str, issue: GitHubIssue
    ) -> list[str]:
        if issue.comments == 0:
            return []
        response = await client.get(
            issue.comments_url, params={"per_page": MAX_COMMENTS_PER_ISSUE}
        )
        self._raise_for_status(response, owner, repo)
        return [c.get("body", "") for c in response.json()[:MAX_COMMENTS_PER_ISSUE]]

    def _raise_for_status(self, response: httpx.Response, owner: str, repo: str) -> None:
        if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
            raise ConnectorError(
                "Limite de taux GitHub atteinte",
                details={"reset_at": response.headers.get("X-RateLimit-Reset")},
            )
        if response.status_code == 404:
            raise ConnectorError(f"Dépôt introuvable : {owner}/{repo}")
        if response.is_error:
            raise ConnectorError(
                f"Erreur API GitHub ({response.status_code})", details={"body": response.text}
            )

    def to_document(self, item: GitHubIssueItem) -> DocumentIn:
        issue = item.issue
        comments_text = "\n\n".join(item.comments)
        content = f"{issue.title}\n\n{issue.body or ''}"
        if comments_text:
            content += f"\n\nCommentaires :\n{comments_text}"
        return DocumentIn(
            source=f"github:{item.owner}/{item.repo}#{issue.number}",
            content=content,
        )
