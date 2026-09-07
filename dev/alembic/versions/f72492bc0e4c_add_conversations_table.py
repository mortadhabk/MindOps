"""add conversations table

Revision ID: f72492bc0e4c
Revises: 252feb9964bf
Create Date: 2026-09-07 11:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f72492bc0e4c'
down_revision: str | Sequence[str] | None = '252feb9964bf'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'conversations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('conversations')
