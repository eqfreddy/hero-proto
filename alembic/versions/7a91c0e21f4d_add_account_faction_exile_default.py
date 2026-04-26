"""add accounts.faction (EXILE default)

Revision ID: 7a91c0e21f4d
Revises: 177a30b78d4a
Create Date: 2026-04-26 09:00:00.000000

Phase 2.5 — narrative faction per account. Defaults all existing rows to
EXILE; new registrations get EXILE via the model default. Phase 3's
level-50 alignment fork transitions players out of EXILE.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7a91c0e21f4d'
down_revision: Union[str, Sequence[str], None] = '177a30b78d4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'faction', sa.String(length=16), nullable=False,
            server_default='EXILE',
        ))


def downgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('faction')
