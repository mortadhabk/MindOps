"""add app_settings table

Revision ID: 252feb9964bf
Revises: 1522a1b5c5d4
Create Date: 2026-09-06 02:32:52.152703

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '252feb9964bf'
down_revision: str | Sequence[str] | None = '1522a1b5c5d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'app_settings',
        sa.Column('section', sa.String(), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('section'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('app_settings')
