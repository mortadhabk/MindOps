"""initial schema

Revision ID: 88a87d7eae19
Revises: 
Create Date: 2026-09-01 11:52:26.586111

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '88a87d7eae19'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
