from pydantic import BaseModel, Field


class GitHubConnectorConfig(BaseModel):
    """Paramètres d'une ConnectorInstance de type "github" (Epic 8) — mêmes noms que les
    paramètres de fetch_items() pour que `connector.fetch_items(**instance.config)` fonctionne
    sans transformation."""

    owner: str = Field(description="Propriétaire du dépôt", examples=["octocat"])
    repo: str = Field(description="Nom du dépôt", examples=["Hello-World"])
    state: str = Field(default="all", description="all | open | closed")


class GitHubComment(BaseModel):
    body: str = ""


class GitHubIssue(BaseModel):
    number: int
    title: str
    body: str | None = ""
    html_url: str
    comments: int = 0
    comments_url: str
    pull_request: dict | None = Field(default=None)

    @property
    def is_pull_request(self) -> bool:
        return self.pull_request is not None
