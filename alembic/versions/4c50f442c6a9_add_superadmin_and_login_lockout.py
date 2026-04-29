"""add superadmin and login lockout fields

Revision ID: 4c50f442c6a9
Revises: d5873b8c911c
Create Date: 2026-04-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4c50f442c6a9'
down_revision: Union[str, Sequence[str], None] = 'd5873b8c911c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_superadmin', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('login_failed_attempts', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('login_locked_until', sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f('ix_accounts_is_superadmin'), ['is_superadmin'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_accounts_is_superadmin'))
        batch_op.drop_column('login_locked_until')
        batch_op.drop_column('login_failed_attempts')
        batch_op.drop_column('is_superadmin')
