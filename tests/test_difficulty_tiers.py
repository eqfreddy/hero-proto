"""Difficulty tier system — enum, display names, XP table, seed."""
from app.models import StageDifficulty, STAGE_TIER_DISPLAY
from app.account_level import XP_PER_BATTLE_WIN, XP_PER_BATTLE_WIN_BY_TIER, xp_per_win


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


def test_xp_table_values():
    assert XP_PER_BATTLE_WIN_BY_TIER[StageDifficulty.NORMAL]    == 12
    assert XP_PER_BATTLE_WIN_BY_TIER[StageDifficulty.HARD]      == 28
    assert XP_PER_BATTLE_WIN_BY_TIER[StageDifficulty.NIGHTMARE] == 50
    assert XP_PER_BATTLE_WIN_BY_TIER[StageDifficulty.LEGENDARY] == 60


def test_xp_per_win_helper():
    assert xp_per_win(StageDifficulty.NORMAL)    == 12
    assert xp_per_win(StageDifficulty.LEGENDARY) == 60
    # Legacy constant kept as NORMAL alias.
    assert XP_PER_BATTLE_WIN == 12


def test_xp_per_win_accepts_strings():
    assert xp_per_win("NORMAL")    == 12
    assert xp_per_win("HARD")      == 28
    assert xp_per_win("NIGHTMARE") == 50
    assert xp_per_win("LEGENDARY") == 60


def test_xp_per_win_unknown_tier_falls_back_to_normal():
    assert xp_per_win("BOGUS") == 12
    assert xp_per_win("")      == 12


def test_xp_grant_lookup_per_tier():
    """Sanity check: tier→XP lookup hits expected values for all four tiers.
    The actual battle-resolve grant sites are covered by the existing battle
    test suite (regression run after wiring changes)."""
    for tier, expected in [
        (StageDifficulty.NORMAL,    12),
        (StageDifficulty.HARD,      28),
        (StageDifficulty.NIGHTMARE, 50),
        (StageDifficulty.LEGENDARY, 60),
    ]:
        assert xp_per_win(tier) == expected
