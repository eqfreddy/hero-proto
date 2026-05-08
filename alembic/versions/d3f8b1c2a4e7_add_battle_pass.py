"""add battle_pass_seasons + account_battle_pass

Revision ID: d3f8b1c2a4e7
Revises: c7a91f3e4d2b
Create Date: 2026-05-08 14:35:00.000000

Phase 5 retention work — Battle Pass infrastructure. Seasons are seeded
on startup; per-account state lazily created on first XP grant or GET.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd3f8b1c2a4e7'
down_revision: Union[str, Sequence[str], None] = 'c7a91f3e4d2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'battle_pass_seasons',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=False, server_default=''),
        sa.Column('starts_at', sa.DateTime(), nullable=False),
        sa.Column('ends_at', sa.DateTime(), nullable=False),
        sa.Column('max_tier', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('xp_per_tier', sa.Integer(), nullable=False, server_default='200'),
        sa.Column('premium_price_cents', sa.Integer(), nullable=False, server_default='999'),
        sa.Column('tracks_json', sa.String(length=16384), nullable=False, server_default='{"free":[],"premium":[]}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('code', name='uq_battle_pass_seasons_code'),
    )
    op.create_index('ix_battle_pass_seasons_code', 'battle_pass_seasons', ['code'])
    op.create_index('ix_battle_pass_seasons_starts_at', 'battle_pass_seasons', ['starts_at'])
    op.create_index('ix_battle_pass_seasons_ends_at', 'battle_pass_seasons', ['ends_at'])
    op.create_index('ix_battle_pass_seasons_is_active', 'battle_pass_seasons', ['is_active'])

    op.create_table(
        'account_battle_pass',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('season_id', sa.Integer(), nullable=False),
        sa.Column('xp_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('claimed_free_json', sa.String(length=2048), nullable=False, server_default='[]'),
        sa.Column('claimed_premium_json', sa.String(length=2048), nullable=False, server_default='[]'),
        sa.Column('premium_purchased_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['season_id'], ['battle_pass_seasons.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('account_id', 'season_id', name='uq_account_battle_pass'),
    )
    op.create_index('ix_account_battle_pass_account_id', 'account_battle_pass', ['account_id'])
    op.create_index('ix_account_battle_pass_season_id', 'account_battle_pass', ['season_id'])


def downgrade() -> None:
    op.drop_index('ix_account_battle_pass_season_id', table_name='account_battle_pass')
    op.drop_index('ix_account_battle_pass_account_id', table_name='account_battle_pass')
    op.drop_table('account_battle_pass')
    op.drop_index('ix_battle_pass_seasons_is_active', table_name='battle_pass_seasons')
    op.drop_index('ix_battle_pass_seasons_ends_at', table_name='battle_pass_seasons')
    op.drop_index('ix_battle_pass_seasons_starts_at', table_name='battle_pass_seasons')
    op.drop_index('ix_battle_pass_seasons_code', table_name='battle_pass_seasons')
    op.drop_table('battle_pass_seasons')
