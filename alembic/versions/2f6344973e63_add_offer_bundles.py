"""add_offer_bundles

Revision ID: 2f6344973e63
Revises: d515d104feb9
Create Date: 2026-04-27 00:08:05.461521

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f6344973e63'
down_revision: Union[str, Sequence[str], None] = 'd515d104feb9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('offer_bundles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.String(length=512), nullable=False),
    sa.Column('price_usd', sa.Float(), nullable=False),
    sa.Column('gems', sa.Integer(), nullable=False),
    sa.Column('shards', sa.Integer(), nullable=False),
    sa.Column('coins', sa.Integer(), nullable=False),
    sa.Column('access_cards', sa.Integer(), nullable=False),
    sa.Column('hero_template_code', sa.String(length=64), nullable=True),
    sa.Column('one_per_account', sa.Boolean(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('available_from', sa.DateTime(), nullable=True),
    sa.Column('available_until', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('offer_bundles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_offer_bundles_active'), ['active'], unique=False)
        batch_op.create_index(batch_op.f('ix_offer_bundles_code'), ['code'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('offer_bundles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_offer_bundles_code'))
        batch_op.drop_index(batch_op.f('ix_offer_bundles_active'))

    op.drop_table('offer_bundles')
