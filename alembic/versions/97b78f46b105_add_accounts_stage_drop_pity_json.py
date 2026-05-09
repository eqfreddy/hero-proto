"""add_accounts_stage_drop_pity_json

Revision ID: 97b78f46b105
Revises: f2b5fa390c66
Create Date: 2026-05-09 11:36:47.821495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97b78f46b105'
down_revision: Union[str, Sequence[str], None] = 'f2b5fa390c66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(
            sa.Column("stage_drop_pity_json", sa.String(length=2048), nullable=False, server_default="{}"),
        )


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("stage_drop_pity_json")
