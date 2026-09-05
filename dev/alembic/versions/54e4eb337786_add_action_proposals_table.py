"""add action_proposals table

Revision ID: 54e4eb337786
Revises: eafcf6557ce4
Create Date: 2026-09-03 11:05:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '54e4eb337786'
down_revision: str | Sequence[str] | None = 'eafcf6557ce4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'action_proposals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('tool_call_id', sa.String(), nullable=False),
        sa.Column('result', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tool_call_id', name='uq_action_proposals_tool_call_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('action_proposals')
