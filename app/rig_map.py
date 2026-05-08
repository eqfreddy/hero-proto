"""Hero template_code -> battle rig mapping.

Single source of truth for which animated rig represents each hero in the
battle viewer. The frontend (`app/static/battle-arena.html`) consumes the
chosen key via `BattleParticipant.rig` and looks it up in its `RIGS` catalog.

Adding a new hero: add a row here AND in `app/seed.py::HERO_SEEDS`. Heroes
without an entry fall back to `DEFAULT_RIG`.
"""
from __future__ import annotations

DEFAULT_RIG = "stick-figure"

RIG_FOR_TEMPLATE: dict[str, str] = {
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


def rig_for(template_code: str | None) -> str:
    if not template_code:
        return DEFAULT_RIG
    return RIG_FOR_TEMPLATE.get(template_code, DEFAULT_RIG)
