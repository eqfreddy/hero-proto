"""add refresh_token fingerprint_hash

Revision ID: c995187a5e15
Revises: 50b27201679e
Create Date: 2026-04-25 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c995187a5e15'
down_revision: Union[str, Sequence[str], None] = '50b27201679e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fingerprint_hash', sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.drop_column('fingerprint_hash')
