"""add collections table + account columns

Revision ID: 7cf6318a80f4
Revises: 97b78f46b105
Create Date: 2026-05-10 01:12:11.034495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cf6318a80f4'
down_revision: Union[str, Sequence[str], None] = '97b78f46b105'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("theme", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("rarity", sa.String(length=16), nullable=False),
        sa.Column("level_bracket", sa.String(length=8), nullable=False),
        sa.Column("pieces_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("reward_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index("ix_collections_sort_order", "collections", ["sort_order"])

    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(
            sa.Column("collection_progress_json", sa.Text(), nullable=False, server_default="{}"),
        )
        batch_op.add_column(
            sa.Column("eight_tracks", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("eight_tracks")
        batch_op.drop_column("collection_progress_json")
    op.drop_index("ix_collections_sort_order", table_name="collections")
    op.drop_table("collections")
