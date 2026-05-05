"""armor_slots_and_named_gear

Renames the old gear slots to a head-to-toe armor system and adds three new
slots (HANDS, WRIST, LEGS). Also adds optional name + flavor columns to gear
so story / raid rewards can be persisted as proper named pieces instead of
overloading stats_json.

Slot rename map:
  HELMET → HEAD
  ARMOR  → CHEST
  BOOTS  → FEET

(WEAPON, RING, AMULET unchanged.)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-29 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SLOT_RENAMES = [
    ("HELMET", "HEAD"),
    ("ARMOR", "CHEST"),
    ("BOOTS", "FEET"),
]


def upgrade() -> None:
    # 1) Rename existing gear rows to the new slot names.
    for old, new in SLOT_RENAMES:
        op.execute(sa.text("UPDATE gear SET slot = :new WHERE slot = :old").bindparams(old=old, new=new))

    # Mailbox payloads can hold "slot": "<value>" too — rewrite those.
    # Stored as JSON inside accounts.mailbox_overflow_json; use a simple string replace.
    # Postgres has json_set / jsonb_replace, SQLite doesn't — go portable with REPLACE().
    for old, new in SLOT_RENAMES:
        op.execute(
            sa.text(
                "UPDATE accounts SET mailbox_overflow_json = REPLACE(mailbox_overflow_json, :old, :new) "
                "WHERE mailbox_overflow_json LIKE :pattern"
            ).bindparams(
                old=f'"slot":"{old}"',
                new=f'"slot":"{new}"',
                pattern=f'%\"slot\":\"{old}\"%',
            )
        )

    # 2) Add name + flavor columns for "named" pieces (story/raid rewards).
    with op.batch_alter_table('gear') as batch:
        batch.add_column(sa.Column('name', sa.String(120), nullable=True))
        batch.add_column(sa.Column('flavor', sa.String(255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('gear') as batch:
        batch.drop_column('flavor')
        batch.drop_column('name')

    # Reverse rename.
    for old, new in SLOT_RENAMES:
        op.execute(sa.text("UPDATE gear SET slot = :old WHERE slot = :new").bindparams(old=old, new=new))
        op.execute(
            sa.text(
                "UPDATE accounts SET mailbox_overflow_json = REPLACE(mailbox_overflow_json, :new, :old) "
                "WHERE mailbox_overflow_json LIKE :pattern"
            ).bindparams(
                old=f'"slot":"{old}"',
                new=f'"slot":"{new}"',
                pattern=f'%\"slot\":\"{new}\"%',
            )
        )
