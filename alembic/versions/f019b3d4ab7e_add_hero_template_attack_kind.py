"""add hero_templates.attack_kind

Revision ID: f019b3d4ab7e
Revises: d8e2f4a5c102
Create Date: 2026-04-26 12:30:00.000000

Phase 3.1 — melee / ranged attack-channel split. Default 'melee' so
existing seeded heroes don't change semantics; specific templates can
opt into 'ranged' via seed updates.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f019b3d4ab7e'
down_revision: Union[str, Sequence[str], None] = 'd8e2f4a5c102'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('hero_templates', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'attack_kind', sa.String(length=8), nullable=False,
            server_default='melee',
        ))


def downgrade() -> None:
    with op.batch_alter_table('hero_templates', schema=None) as batch_op:
        batch_op.drop_column('attack_kind')
