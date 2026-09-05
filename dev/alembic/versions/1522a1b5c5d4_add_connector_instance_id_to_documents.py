"""add connector_instance_id to documents

Revision ID: 1522a1b5c5d4
Revises: 923a66d0f9d1
Create Date: 2026-09-05 18:32:56.884348

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1522a1b5c5d4'
down_revision: str | Sequence[str] | None = '923a66d0f9d1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK_NAME = 'fk_documents_connector_instance_id'


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('documents', sa.Column('connector_instance_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        FK_NAME,
        'documents',
        'connector_instances',
        ['connector_instance_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(FK_NAME, 'documents', type_='foreignkey')
    op.drop_column('documents', 'connector_instance_id')
