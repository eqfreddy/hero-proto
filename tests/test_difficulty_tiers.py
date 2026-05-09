"""Difficulty tier system — enum, display names, XP table, seed."""
from app.models import StageDifficulty, STAGE_TIER_DISPLAY


def test_legendary_in_enum():
    assert StageDifficulty.LEGENDARY == "LEGENDARY"
    assert {t.value for t in StageDifficulty} == {"NORMAL", "HARD", "NIGHTMARE", "LEGENDARY"}


def test_display_names_cover_all_tiers():
    assert STAGE_TIER_DISPLAY[StageDifficulty.NORMAL] == "Floppy"
    assert STAGE_TIER_DISPLAY[StageDifficulty.HARD] == "Hard Disk"
    assert STAGE_TIER_DISPLAY[StageDifficulty.NIGHTMARE] == "RAID-0"
    assert STAGE_TIER_DISPLAY[StageDifficulty.LEGENDARY] == "Legen'waitforit'dary"
    # Every enum value must have a display name.
    for t in StageDifficulty:
        assert t in STAGE_TIER_DISPLAY
