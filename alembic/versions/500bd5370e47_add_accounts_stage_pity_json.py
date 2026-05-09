"""add accounts.stage_pity_json

Revision ID: 500bd5370e47
Revises: c4f7d8a3e2b9
Create Date: 2026-05-09 09:56:27.184823

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '500bd5370e47'
down_revision: Union[str, Sequence[str], None] = 'c4f7d8a3e2b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stage_pity_json', sa.String(length=2048), nullable=False, server_default='{}'))


def downgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('stage_pity_json')
