"""Per-account rate limit on /battles — Sprint A."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import deps as deps_mod
from app.middleware import TokenBucket


class _FakeAccount:
    def __init__(self, account_id: int) -> None:
        self.id = account_id


def _install_bucket(monkeypatch: pytest.MonkeyPatch, limit: int) -> None:
    monkeypatch.setattr(deps_mod, "_battle_bucket", TokenBucket(limit_per_minute=limit))
    # Simulate a non-test env so the env short-circuit in the dep doesn't kick in.
    monkeypatch.setattr(deps_mod.settings, "environment", "dev")
    monkeypatch.setattr(deps_mod.settings, "rate_limit_disabled", False)


def test_bucket_allows_up_to_limit_then_429(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_bucket(monkeypatch, limit=3)
    acct = _FakeAccount(1)

    for _ in range(3):
        deps_mod.enforce_battle_rate_limit(acct)

    with pytest.raises(HTTPException) as exc:
        deps_mod.enforce_battle_rate_limit(acct)
    assert exc.value.status_code == 429
    assert "rate limit" in exc.value.detail.lower()


def test_bucket_is_per_account(monkeypatch: pytest.MonkeyPatch) -> None:
    """Account 2 must not be blocked by account 1's hammering."""
    _install_bucket(monkeypatch, limit=2)
    a1 = _FakeAccount(1)
    a2 = _FakeAccount(2)

    deps_mod.enforce_battle_rate_limit(a1)
    deps_mod.enforce_battle_rate_limit(a1)
    with pytest.raises(HTTPException):
        deps_mod.enforce_battle_rate_limit(a1)

    # Different account — fresh budget.
    deps_mod.enforce_battle_rate_limit(a2)
    deps_mod.enforce_battle_rate_limit(a2)


def test_rate_limit_disabled_bypasses(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_bucket(monkeypatch, limit=1)
    monkeypatch.setattr(deps_mod.settings, "rate_limit_disabled", True)
    acct = _FakeAccount(1)
    for _ in range(5):
        deps_mod.enforce_battle_rate_limit(acct)


def test_test_env_bypasses(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_bucket(monkeypatch, limit=1)
    monkeypatch.setattr(deps_mod.settings, "environment", "test")
    acct = _FakeAccount(1)
    for _ in range(5):
        deps_mod.enforce_battle_rate_limit(acct)


# --- Sprint B: arena + guild-message buckets follow the same pattern. ---


def test_arena_bucket_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps_mod, "_arena_bucket", TokenBucket(limit_per_minute=2))
    monkeypatch.setattr(deps_mod.settings, "environment", "dev")
    monkeypatch.setattr(deps_mod.settings, "rate_limit_disabled", False)
    acct = _FakeAccount(10)
    deps_mod.enforce_arena_rate_limit(acct)
    deps_mod.enforce_arena_rate_limit(acct)
    with pytest.raises(HTTPException) as exc:
        deps_mod.enforce_arena_rate_limit(acct)
    assert exc.value.status_code == 429
    assert "arena attack" in exc.value.detail.lower()


def test_guild_message_bucket_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps_mod, "_guild_msg_bucket", TokenBucket(limit_per_minute=2))
    monkeypatch.setattr(deps_mod.settings, "environment", "dev")
    monkeypatch.setattr(deps_mod.settings, "rate_limit_disabled", False)
    acct = _FakeAccount(11)
    deps_mod.enforce_guild_message_rate_limit(acct)
    deps_mod.enforce_guild_message_rate_limit(acct)
    with pytest.raises(HTTPException) as exc:
        deps_mod.enforce_guild_message_rate_limit(acct)
    assert exc.value.status_code == 429
    assert "guild chat" in exc.value.detail.lower()


def test_buckets_are_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Battle bucket full must not block arena or guild-chat."""
    monkeypatch.setattr(deps_mod, "_battle_bucket", TokenBucket(limit_per_minute=1))
    monkeypatch.setattr(deps_mod, "_arena_bucket", TokenBucket(limit_per_minute=5))
    monkeypatch.setattr(deps_mod, "_guild_msg_bucket", TokenBucket(limit_per_minute=5))
    monkeypatch.setattr(deps_mod.settings, "environment", "dev")
    monkeypatch.setattr(deps_mod.settings, "rate_limit_disabled", False)
    acct = _FakeAccount(12)

    deps_mod.enforce_battle_rate_limit(acct)
    with pytest.raises(HTTPException):
        deps_mod.enforce_battle_rate_limit(acct)
    # Arena + chat still open for the same account.
    deps_mod.enforce_arena_rate_limit(acct)
    deps_mod.enforce_guild_message_rate_limit(acct)
