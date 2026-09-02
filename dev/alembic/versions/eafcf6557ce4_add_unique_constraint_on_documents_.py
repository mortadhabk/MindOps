"""add unique constraint on documents source

Revision ID: eafcf6557ce4
Revises: 5d62431598da
Create Date: 2026-09-02 10:27:54.903180

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'eafcf6557ce4'
down_revision: str | Sequence[str] | None = '5d62431598da'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Un meme `source` a pu etre ingere plusieurs fois avant l'ajout de cette contrainte
    # (ex : sync connecteur relancee sans deduplication) -> on ne garde que la ligne la
    # plus recente par source avant de rendre la colonne unique.
    op.execute(
        "DELETE FROM documents d USING documents d2 "
        "WHERE d.source = d2.source AND d.id < d2.id"
    )
    op.create_unique_constraint('uq_documents_source', 'documents', ['source'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_documents_source', 'documents', type_='unique')
