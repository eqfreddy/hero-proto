"""Tests for rig_map — the source of truth for hero -> battle rig keys."""
from __future__ import annotations

from app.rig_map import DEFAULT_RIG, RIG_FOR_TEMPLATE, rig_for
from app.seed import HERO_SEEDS


def test_rig_for_known_template():
    assert rig_for("ticket_gremlin") == "kunoichi"
    assert rig_for("keymaster_gary") == "stick-figure"


def test_rig_for_unknown_falls_back_to_default():
    assert rig_for("not_a_real_hero") == DEFAULT_RIG


def test_rig_for_none_or_empty():
    assert rig_for(None) == DEFAULT_RIG
    assert rig_for("") == DEFAULT_RIG


def test_every_seeded_hero_has_a_rig():
    """If a hero ships in HERO_SEEDS without a rig entry it'll fall back to
    the stick-figure default — fine, but we want to know about it."""
    missing = [h["code"] for h in HERO_SEEDS if h["code"] not in RIG_FOR_TEMPLATE]
    assert missing == [], (
        f"{len(missing)} seeded heroes have no rig_map entry: {missing[:10]}"
    )
