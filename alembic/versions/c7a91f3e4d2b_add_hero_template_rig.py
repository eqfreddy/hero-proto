"""add hero_templates.rig

Revision ID: c7a91f3e4d2b
Revises: a4e1c5d2b8f9
Create Date: 2026-05-08 14:10:00.000000

Promotes the rig assignment from `app/rig_map.py` (in-memory dict) to a
column on `hero_templates`. Backfills existing rows from the dict so the
data layer becomes the source of truth — adding new heroes via `seed.py`
no longer requires editing a separate map.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7a91f3e4d2b'
down_revision: Union[str, Sequence[str], None] = 'a4e1c5d2b8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_RIG = "stick-figure"

RIG_FOR_TEMPLATE = {
    "dark-assassin":            "dark-assassin",
    "ticket_gremlin":           "kunoichi",
    "printer_whisperer":        "wanderer-magican",
    "overnight_janitor":        "ninja-monk",
    "jaded_intern":             "satyr-1",
    "sre_on_call":              "fire-wizard",
    "midnight_pager":           "karasu-tengu",
    "helpdesk_veteran":         "knight-1",
    "the_sysadmin":             "lightning-mage",
    "the_consultant":           "gorgon-1",
    "the_founder":              "minotaur-1",
    "the_board_member":         "minotaur-3",
    "chaos_monkey":             "red-werewolf",
    "compliance_officer":       "knight-3",
    "security_auditor":         "knight-2",
    "agile_coach":              "satyr-2",
    "forgotten_contractor":     "ninja-peasant",
    "rogue_dba":                "black-werewolf",
    "keymaster_gary":           "stick-figure",
    "applecrumb":               "kitsune",
    "the_whistleblower":        "dark-assassin",
    "root_access_janitor":      "minotaur-2",
    "shadow_it_operator":       "kunoichi",
    "vp_of_vibes":              "satyr-3",
    "frontline_l1_tech":        "knight-2",
    "build_engineer":           "fire-wizard",
    "devops_apprentice":        "ninja-peasant",
    "on_call_martyr":           "karasu-tengu",
    "oncall_warrior":           "knight-1",
    "cert_collector":           "knight-3",
    "database_archaeologist":   "yamabushi-tengu",
    "blue_team_lead":           "knight-2",
    "office_coffee_hoarder":    "satyr-1",
    "retired_mainframe_guru":   "wanderer-magican",
    "tape_library_ghost":       "yamabushi-tengu",
    "the_post_mortem":          "dark-assassin",
    "the_successor":            "knight-1",
    "raidboss_c_suite_hydra":   "minotaur-3",
    "raidboss_chaos_dragon":    "red-werewolf",
    "raidboss_legacy_colossus": "minotaur-1",
    "tbfam":                    "gorgon-2",
}


def upgrade() -> None:
    with op.batch_alter_table('hero_templates', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'rig', sa.String(length=64), nullable=False,
            server_default=DEFAULT_RIG,
        ))

    bind = op.get_bind()
    for code, rig in RIG_FOR_TEMPLATE.items():
        bind.execute(
            sa.text("UPDATE hero_templates SET rig = :rig WHERE code = :code"),
            {"rig": rig, "code": code},
        )


def downgrade() -> None:
    with op.batch_alter_table('hero_templates', schema=None) as batch_op:
        batch_op.drop_column('rig')
