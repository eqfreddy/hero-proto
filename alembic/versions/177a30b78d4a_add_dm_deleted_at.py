"""add direct_messages.deleted_at

Revision ID: 177a30b78d4a
Revises: c995187a5e15
Create Date: 2026-04-26 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '177a30b78d4a'
down_revision: Union[str, Sequence[str], None] = 'c995187a5e15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('direct_messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('direct_messages', schema=None) as batch_op:
        batch_op.drop_column('deleted_at')
