"""add_gear_locked

Adds a `locked` boolean to the gear table so players can protect pieces
from accidental salvage. Defaults to 0 (unlocked) for all existing rows.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('gear', sa.Column('locked', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('gear', 'locked')
