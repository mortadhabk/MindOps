"""add connector_instances table

Revision ID: 923a66d0f9d1
Revises: 21fcbb804a17
Create Date: 2026-09-05 13:55:29.479511

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '923a66d0f9d1'
down_revision: str | Sequence[str] | None = '21fcbb804a17'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'connector_instances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('connector_type', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('position_x', sa.Float(), nullable=False),
        sa.Column('position_y', sa.Float(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('last_result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('connector_instances')
