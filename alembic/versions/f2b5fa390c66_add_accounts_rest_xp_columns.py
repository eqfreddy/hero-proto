"""add accounts rest_xp columns

Revision ID: f2b5fa390c66
Revises: 500bd5370e47
Create Date: 2026-05-09 10:38:00.686851

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2b5fa390c66'
down_revision: Union[str, Sequence[str], None] = '500bd5370e47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("rest_xp_banked_seconds", sa.Integer(), nullable=False, server_default="0"),
        )
        batch_op.add_column(
            sa.Column("rest_xp_last_tick_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )


def downgrade() -> None:
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.drop_column("rest_xp_last_tick_at")
        batch_op.drop_column("rest_xp_banked_seconds")
