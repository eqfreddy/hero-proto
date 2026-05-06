"""add_quest_tables

Revision ID: db7eac125e36
Revises: c3d4e5f6a7b8
Create Date: 2026-05-06 11:25:48.235179

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db7eac125e36'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'quests',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.String(512), nullable=False, server_default=''),
        sa.Column('tasks_json', sa.String(8192), nullable=False, server_default='[]'),
        sa.Column('reward_json', sa.String(2048), nullable=False, server_default='{}'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_table(
        'account_quests',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quest_id', sa.String(64), sa.ForeignKey('quests.id'), nullable=False),
        sa.Column('progress_json', sa.String(4096), nullable=False, server_default='{}'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('claimed_at', sa.DateTime(), nullable=True),
        sa.Column('claim_choice', sa.String(16), nullable=True),
        sa.Column('dismissed', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('account_id', 'quest_id', name='uq_account_quests_account_quest'),
    )
    op.create_index('ix_account_quests_account_id', 'account_quests', ['account_id'])


def downgrade() -> None:
    op.drop_table('account_quests')
    op.drop_table('quests')
