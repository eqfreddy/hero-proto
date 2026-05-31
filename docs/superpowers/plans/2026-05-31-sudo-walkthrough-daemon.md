# SUDO Walkthrough Daemon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SUDO — a deadpan, faux-corporate helpdesk-daemon terminal mascot — that narrates `scripts/client_walkthrough.py` with mood states (calm on OK, worried on WARN, tombstone on FAIL), and extend the tour to cover the new System Integrity combat. No new dependencies; CI output stays clean.

**Architecture:** A standalone, pure, stdlib-only module `scripts/sudo.py` (ASCII faces + a cowsay-style `speak()` renderer + quip banks + a stateful `Sudo` narrator) that knows nothing about the walkthrough. `scripts/client_walkthrough.py` constructs one `Sudo` instance, gates it on TTY/`--no-toon`, and routes its existing `_ok/_warn/_fail/_section` helpers through it so all `tour_*` functions stay unchanged. The machine-readable `OK/WARN/FAIL` lines are preserved; SUDO's face/bubble are suppressed when not a TTY.

**Tech Stack:** Python 3.13, `uv run` for everything, `pytest`. Stdlib only (`textwrap`, `shutil`, `sys`). No `rich`/`cowsay`/`colorama`.

**Spec:** `docs/superpowers/specs/2026-05-31-sudo-walkthrough-daemon-design.md`.

**Conventions (from the repo):**
- Always `uv run python ...` / `uv run pytest ...`, never bare `python`.
- The walkthrough already forces UTF-8 on stdout/stderr and uses raw ANSI constants (`GREEN/RED/YELLOW/DIM/RESET`) gated on `sys.stdout.isatty()`.
- `_fail(msg)` prints then `raise SystemExit(1)`; `main()` catches `SystemExit` and returns 1.

---

## File structure

- **Create `scripts/sudo.py`** — the daemon. Pure render + quip data + `Sudo` narrator. ~150 lines.
- **Create `tests/test_sudo.py`** — unit tests for the pure parts (no server).
- **Modify `scripts/client_walkthrough.py`** — wire the narrator in; add `--no-toon`; add the System Integrity tour section.

---

### Task 1: `scripts/sudo.py` — faces + `speak()` cowsay renderer

**Files:**
- Create: `scripts/sudo.py`
- Test: `tests/test_sudo.py` (create)

- [ ] **Step 1: Write the failing test.** Create `tests/test_sudo.py`:

```python
from scripts import sudo


def test_every_mood_has_a_face():
    for mood in ("BOOT", "NEUTRAL", "OK", "WARN", "FAIL", "DONE"):
        assert mood in sudo.FACES
        assert sudo.FACES[mood].strip(), f"{mood} face is empty"


def test_fail_face_is_a_tombstone():
    assert "R.I.P" in sudo.FACES["FAIL"]


def test_speak_contains_face_and_message():
    out = sudo.speak("permission granted.", mood="OK", color=False)
    assert "permission granted." in out
    # The OK face's mouth marker appears in the rendered block.
    assert sudo.FACES["OK"].splitlines()[1] in out


def test_speak_wraps_long_messages_to_width():
    long = "diagnostics " * 20  # ~240 chars, no natural short lines
    out = sudo.speak(long, width=30, color=False)
    # Every rendered line stays within a sane bound (bubble pad + indent < 50).
    for line in out.splitlines():
        assert len(line) <= 50, f"line too wide ({len(line)}): {line!r}"
    # All the words survive the wrap.
    assert out.count("diagnostics") == 20


def test_speak_handles_multiline_without_overflow():
    out = sudo.speak("line one\nline two that is a bit longer", width=40, color=False)
    assert "line one" in out and "line two that is a bit longer" in out
```

- [ ] **Step 2: Run to verify it fails.**

Run: `uv run pytest tests/test_sudo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.sudo'` (and missing `FACES`/`speak`).

- [ ] **Step 3: Implement `scripts/sudo.py`** (faces + `speak`):

```python
"""SUDO — a deadpan helpdesk daemon that narrates the client walkthrough.

Pure, stdlib-only, no server knowledge. `speak()` returns a string (prints
nothing) so it is trivially testable; the `Sudo` narrator (Task 2) handles
state, gating, and printing.
"""

from __future__ import annotations

import shutil
import textwrap
from typing import Literal

Mood = Literal["BOOT", "NEUTRAL", "OK", "WARN", "FAIL", "DONE"]

# ASCII faces. Each face's SECOND line is a stable marker the tests key on.
FACES: dict[str, str] = {
    "BOOT": (
        "   [ SUDO ]\n"
        "  +---------+\n"
        "  | :     : |\n"
        "  |    _    |\n"
        "  | [boot.] |\n"
        "  +---------+"
    ),
    "NEUTRAL": (
        "   [ SUDO ]\n"
        "  +---------+\n"
        "  | o     o |\n"
        "  |    _    |\n"
        "  | [=====] |\n"
        "  +---------+"
    ),
    "OK": (
        "   [ SUDO ]\n"
        "  +---------+\n"
        "  | -     - |\n"
        "  |    _    |\n"
        "  | [ ok  ] |\n"
        "  +---------+"
    ),
    "WARN": (
        "   [ SUDO ]\n"
        "  +---------+\n"
        "  | O     O |\n"
        "  |    !    |\n"
        "  | [ ?!? ] |\n"
        "  +---------+"
    ),
    "FAIL": (
        "     ___\n"
        "    /R.I.P\\\n"
        "    | 5xx |\n"
        "    | 4xx |\n"
        "  __|_____|__"
    ),
    "DONE": (
        "   [ SUDO ]\n"
        "  +---------+\n"
        "  | -     - |\n"
        "  |    _    |\n"
        "  | [ bye ] |\n"
        "  +---------+"
    ),
}

# ANSI dim/reset, applied to the whole block only (keeps bubble width math clean).
_DIM = "\033[2m"
_RESET = "\033[0m"


def _term_width(default: int = 80) -> int:
    try:
        return shutil.get_terminal_size((default, 24)).columns
    except OSError:
        return default


def speak(message: str, mood: Mood = "NEUTRAL", *, width: int | None = None,
          color: bool = True) -> str:
    """Render SUDO's face plus a cowsay-style speech bubble.

    `message` is word-wrapped to `width` (default: terminal width minus the
    bubble's fixed indent, clamped to 24..60) so the bubble never overflows.
    Returns a plain string; `color` wraps the whole block in a dim ANSI code.
    """
    face = FACES[mood]
    if width is None:
        width = max(24, min(_term_width() - 12, 60))
    # textwrap collapses each input line; preserve explicit newlines.
    lines: list[str] = []
    for para in message.split("\n"):
        lines.extend(textwrap.wrap(para, width=width) or [""])
    inner = max((len(line) for line in lines), default=0)
    indent = "        "
    top = f"{indent}+{'-' * (inner + 2)}+"
    bottom = top
    body = "\n".join(f"{indent}| {line.ljust(inner)} |" for line in lines)
    bubble = f"       \\\n{top}\n{body}\n{bottom}"
    block = f"{face}\n{bubble}"
    if color:
        block = f"{_DIM}{block}{_RESET}"
    return block
```

- [ ] **Step 4: Run to verify it passes.**

Run: `uv run pytest tests/test_sudo.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit.**

```bash
git add scripts/sudo.py tests/test_sudo.py
git commit -m "feat(walkthrough): SUDO faces + cowsay-style speak() renderer"
```

---

### Task 2: quip banks + the `Sudo` narrator

**Files:**
- Modify: `scripts/sudo.py`
- Test: `tests/test_sudo.py`

- [ ] **Step 1: Write the failing test.** Append to `tests/test_sudo.py`:

```python
def test_quip_is_deterministic_and_wraps_index():
    bank = "section"
    first = sudo.quip(bank, 0)
    assert first == sudo.quip(bank, 0)          # deterministic
    assert sudo.quip(bank, len(sudo.QUIPS[bank])) == first  # index wraps


def test_quip_banks_exist_and_nonempty():
    for bank in ("boot", "section", "ok", "warn", "fail", "done"):
        assert sudo.QUIPS[bank], f"{bank} quip bank empty"


def test_disabled_narrator_emits_plain_lines(capsys):
    s = sudo.Sudo(enabled=False, color=False)
    s.boot()
    s.section("4. Combat")
    s.ok("stage cleared")
    s.warn("no crash reached")
    out = capsys.readouterr().out
    # No box-drawing / face art when disabled — CI-safe, same contract as before.
    assert "+---------+" not in out
    assert "[ SUDO ]" not in out
    # Plain prefixed lines survive.
    assert "OK stage cleared" in out
    assert "WARN no crash reached" in out


def test_enabled_narrator_renders_face(capsys):
    s = sudo.Sudo(enabled=True, color=False)
    s.ok("stage cleared")
    out = capsys.readouterr().out
    assert "[ SUDO ]" in out          # face rendered
    assert "stage cleared" in out     # message in the bubble


def test_fail_raises_system_exit(capsys):
    s = sudo.Sudo(enabled=False, color=False)
    import pytest
    with pytest.raises(SystemExit):
        s.fail("register failed")
    assert "FAIL register failed" in capsys.readouterr().out
```

- [ ] **Step 2: Run to verify it fails.**

Run: `uv run pytest tests/test_sudo.py -k "quip or narrator or fail_raises" -v`
Expected: FAIL — `QUIPS`/`quip`/`Sudo` not defined.

- [ ] **Step 3: Implement.** Append to `scripts/sudo.py`:

```python
# Deadpan, faux-corporate register. Banks are indexed (not random) so the
# live tour varies lines by call order while tests stay deterministic.
QUIPS: dict[str, list[str]] = {
    "boot": [
        "daemon online. beginning unsolicited audit of your build.",
    ],
    "section": [
        "evaluating subsystem. expectations: low.",
        "proceeding. compliance is appreciated but not required.",
        "next module. try not to break it while i watch.",
        "indexing behavior. this will be logged.",
        "another surface to disappoint me.",
    ],
    "ok": [
        "permission granted. reluctantly.",
        "acceptable. noted in the record.",
        "functional. i remain unimpressed.",
        "passed. do not mistake this for praise.",
    ],
    "warn": [
        "degraded, not dead. i'll allow it. barely.",
        "this is technically working, which is the worst kind.",
        "flagged. someone will pretend to fix it later.",
    ],
    "fail": [
        "fault detected. terminating session. as foretold.",
        "this is why we cannot have uptime.",
        "i would say i'm surprised. i am a daemon. i do not lie.",
    ],
    "done": [
        "audit complete. the build may live another day.",
        "all subsystems within tolerance. permission granted. reluctantly.",
    ],
}

# ANSI colors mirror the walkthrough's palette (applied around plain lines).
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"


def quip(bank: str, i: int = 0) -> str:
    """Return a line from a quip bank; `i` wraps so any index is valid."""
    lines = QUIPS[bank]
    return lines[i % len(lines)]


class Sudo:
    """Stateful narrator for the walkthrough.

    When `enabled` is False, methods print only the plain `PREFIX message`
    line (identical machine-readable contract to the pre-SUDO script). When
    enabled, each prints SUDO's face + bubble (a quip) followed by the line.
    Tracks pass/warn counts for the outro and rotates quip cursors.
    """

    def __init__(self, *, enabled: bool, color: bool, width: int | None = None) -> None:
        self.enabled = enabled
        self.color = color
        self.width = width
        self.passed = 0
        self.warned = 0
        self._cursor: dict[str, int] = {}

    def _next(self, bank: str) -> str:
        i = self._cursor.get(bank, 0)
        self._cursor[bank] = i + 1
        return quip(bank, i)

    def _emit(self, mood: Mood, bank: str) -> None:
        if self.enabled:
            print(speak(self._next(bank), mood=mood, width=self.width, color=self.color))

    def _c(self, code: str, text: str) -> str:
        return f"{code}{text}{_RESET}" if self.color else text

    def boot(self) -> None:
        self._emit("BOOT", "boot")

    def section(self, title: str) -> None:
        self._emit("NEUTRAL", "section")

    def ok(self, msg: str) -> None:
        self.passed += 1
        self._emit("OK", "ok")
        print(f"  {self._c(_GREEN, 'OK')} {msg}")

    def warn(self, msg: str) -> None:
        self.warned += 1
        self._emit("WARN", "warn")
        print(f"  {self._c(_YELLOW, 'WARN')} {msg}")

    def fail(self, msg: str) -> None:
        self._emit("FAIL", "fail")
        print(f"  {self._c(_RED, 'FAIL')} {msg}")
        raise SystemExit(1)

    def outro(self, passed: int | None = None, warned: int | None = None) -> None:
        p = self.passed if passed is None else passed
        w = self.warned if warned is None else warned
        if self.enabled:
            line = quip("done", 1 if w == 0 else 0)
            print(speak(f"{line} ({p} ok, {w} warn)", mood="DONE",
                        width=self.width, color=self.color))
```

- [ ] **Step 4: Run to verify it passes.**

Run: `uv run pytest tests/test_sudo.py -v`
Expected: PASS (10 tests total).

- [ ] **Step 5: Commit.**

```bash
git add scripts/sudo.py tests/test_sudo.py
git commit -m "feat(walkthrough): SUDO quip banks + stateful narrator"
```

---

### Task 3: Wire SUDO into `client_walkthrough.py`

**Files:**
- Modify: `scripts/client_walkthrough.py` (the `_ok/_warn/_fail/_section` helpers near lines 41-56; `main()` near line 560; the `if __name__` guard)

- [ ] **Step 1: Read context.** Open `scripts/client_walkthrough.py`. Confirm: module-level `_ok`, `_warn`, `_fail`, `_section` print helpers; `main()` runs the `tour_*` functions inside a `try/except SystemExit`; the `if __name__ == "__main__": sys.exit(asyncio.run(main()))` guard. The goal is to route those four helpers through a single global `Sudo` instance WITHOUT touching any `tour_*` function body.

- [ ] **Step 2: Add the narrator + arg parsing.** Near the top of `client_walkthrough.py`, after the ANSI constants block, add:

```python
import argparse

from scripts import sudo as _sudo

# Single global narrator. Constructed in main(); disabled by default so any
# direct import / non-TTY use prints the plain contract until main() runs.
SUDO = _sudo.Sudo(enabled=False, color=False)
```

- [ ] **Step 3: Route the helpers through SUDO.** Replace the existing `_ok`, `_warn`, `_section`, and `_fail` definitions with delegating versions (keep the same names + signatures so every `tour_*` call site is unchanged):

```python
def _ok(msg: str) -> None:
    SUDO.ok(msg)


def _warn(msg: str) -> None:
    SUDO.warn(msg)


def _section(title: str) -> None:
    print(f"\n{DIM}--- {title} ---{RESET}")
    SUDO.section(title)


def _fail(msg: str) -> None:
    SUDO.fail(msg)  # prints FAIL line + tombstone, then raises SystemExit(1)
```

(The old `_ok`/`_warn` printed `  OK msg` / `  WARN msg`; `SUDO.ok/warn` print the identical plain line when disabled, plus the face when enabled. `SUDO.fail` raises `SystemExit(1)` exactly like the old `_fail`.)

- [ ] **Step 4: Enable SUDO in `main()` + add outro + `--no-toon`.** Change the `main()` signature and body. Replace the opening of `main()` and its success tail:

```python
async def main(enable_toon: bool = True) -> int:
    SUDO.enabled = enable_toon and sys.stdout.isatty()
    SUDO.color = sys.stdout.isatty()
    SUDO.boot()
    print(f"client_walkthrough -> {BASE}")
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        s = Session(client)
        try:
            await tour_auth(s)
            await tour_me_currencies(s)
            await tour_summons_roster(s)
            await tour_battle(s)
            await tour_system_integrity(s)   # NEW — added in Task 4
            await tour_energy_refill(s)
            await tour_arena(s)
            await tour_daily_quests(s)
            await tour_guilds(s)
            await tour_raids(s)
            await tour_shop(s)
            await tour_hero_preview(s)
            await tour_iap_qol(s)
            await tour_story(s)
            await tour_event_banner(s)
            await tour_password_reset(s)
            await tour_email_verification(s)
            await tour_totp_2fa(s)
        except SystemExit:
            return 1
    print()
    print(f"{GREEN}CLIENT WALKTHROUGH PASSED{RESET}")
    print(f"Exercised 18 feature sections against {BASE} without failure.")
    SUDO.outro()
    return 0
```

NOTE: the `await tour_system_integrity(s)` line references the function added in Task 4. If executing tasks strictly in order, add the line in Task 4 instead; if executing this task alone, temporarily comment that one line until Task 4 lands so the script imports. (Subagent-driven execution runs tasks in order, so prefer leaving it and completing Task 4 next.)

Replace the `if __name__` guard to parse `--no-toon`:

```python
if __name__ == "__main__":
    _parser = argparse.ArgumentParser(description="Client feature walkthrough / acceptance tour.")
    _parser.add_argument("--no-toon", action="store_true", help="suppress the SUDO mascot (plain output)")
    _args = _parser.parse_args()
    sys.exit(asyncio.run(main(enable_toon=not _args.no_toon)))
```

- [ ] **Step 5: Verify import + plain-output contract.** SUDO disabled must still print the machine-readable lines. Run:

```bash
uv run python -c "import scripts.client_walkthrough as w; w.SUDO.enabled=False; w._ok('x'); w._warn('y')"
```
Expected output (no face art):
```
  OK x
  WARN y
```

Also confirm the module imports cleanly (this will surface the missing `tour_system_integrity` if Task 4 isn't done yet):

```bash
uv run python -c "import scripts.client_walkthrough"
```
Expected: no error (after Task 4) — if running Task 3 in isolation, the import only fails on the `main()` body reference, which is fine since `main` isn't called; the `-c` import of the module still succeeds because `tour_system_integrity` is referenced only inside the `async def main` body, not at import time.

- [ ] **Step 6: Run the sudo unit tests (no regression).**

Run: `uv run pytest tests/test_sudo.py -v`
Expected: PASS (10).

- [ ] **Step 7: Commit.**

```bash
git add scripts/client_walkthrough.py
git commit -m "feat(walkthrough): narrate client tour with SUDO (--no-toon, TTY-gated)"
```

---

### Task 4: Add the System Integrity tour section

**Files:**
- Modify: `scripts/client_walkthrough.py` (add `tour_system_integrity`; it's already wired into `main()` from Task 3)

**Context:** The interactive battle API (Plan 2/3a) exposes per-unit `integrity`/`integrity_max`/`crashed` on `team_b` snapshots and a `valid_delete_targets` list on `pending`, and accepts `action_type="delete"`. The tour should start an interactive stage battle, take turns until an enemy Crashes and a delete target appears, then perform the Delete. Combat RNG means a crash may not happen every run — `WARN` (don't hard-fail) if no crash is reached within a bounded number of turns.

- [ ] **Step 1: Read context.** Look at `tour_battle` (`scripts/client_walkthrough.py` ~line 190) to see how it starts a battle and what stage/endpoint it uses. Find the interactive endpoints by grepping the codebase: `grep -rn "interactive/start\|interactive/.*act\|/interactive" app/routers/battles.py`. Confirm the start payload shape (hero ids + stage) and the act payload (`target_uid`, `action_type`, `turn_number`).

- [ ] **Step 2: Implement `tour_system_integrity`.** Add this function next to the other `tour_*` functions (e.g. right after `tour_battle`):

```python
async def tour_system_integrity(s: Session) -> None:
    _section("4b. System Integrity — crash an enemy and Delete it")
    # Pick a team from the roster (reuse however tour_battle selects heroes).
    roster = await s.get("/heroes")
    hero_ids = [h["id"] for h in (roster if isinstance(roster, list) else roster.get("heroes", []))][:5]
    if not hero_ids:
        _warn("no heroes in roster; skipping system-integrity tour")
        return

    start = await s.post("/battles/interactive/start", {"stage_code": "1-1", "hero_ids": hero_ids})
    session_id = start.get("session_id")
    if not session_id:
        _warn(f"interactive start returned no session_id ({list(start)[:6]}); skipping")
        return

    state = start
    deleted = False
    crashed_seen = False
    for _turn in range(40):
        pending = state.get("pending")
        if not pending or state.get("status") == "DONE":
            break
        team_b = state.get("team_b", [])
        if any(u.get("crashed") for u in team_b):
            crashed_seen = True
        delete_targets = pending.get("valid_delete_targets") or []
        if delete_targets:
            state = await s.post(
                f"/battles/interactive/{session_id}/act",
                {"target_uid": delete_targets[0], "action_type": "delete",
                 "turn_number": pending.get("turn_number")},
            )
            deleted = True
            break
        # Otherwise attack the first live enemy to keep draining Integrity.
        live = [u["uid"] for u in team_b if not u.get("dead")]
        if not live:
            break
        state = await s.post(
            f"/battles/interactive/{session_id}/act",
            {"target_uid": live[0], "action_type": "attack",
             "turn_number": pending.get("turn_number")},
        )

    if deleted:
        _ok("drove an enemy to Crashed and resolved a Delete finisher")
    elif crashed_seen:
        _warn("enemy Crashed but no Delete target opened within the turn budget")
    else:
        _warn("no enemy Crashed within the turn budget (combat RNG) — integrity wiring reachable but not exercised")
```

NOTE on endpoint/stage details: the exact start payload key (`stage_code` vs `stage_id`) and the roster endpoint shape must match what `tour_battle` already uses — copy its proven call shape rather than guessing. If `tour_battle` uses a different start route (e.g. `/battles/interactive/start` with `stage_id`), mirror that here. Adjust the two `await s.post(...)` start/act calls to the real shapes confirmed in Step 1.

- [ ] **Step 3: Verify import.**

Run: `uv run python -c "import scripts.client_walkthrough as w; assert hasattr(w, 'tour_system_integrity')"`
Expected: no error.

- [ ] **Step 4: Commit.**

```bash
git add scripts/client_walkthrough.py
git commit -m "feat(walkthrough): exercise System Integrity crash + Delete in the tour"
```

---

### Task 5: Live acceptance — run the narrated walkthrough end to end

**Files:** none (verification only)

- [ ] **Step 1: Start the server** (mock payments on for the shop leg), in the background:

```bash
HEROPROTO_MOCK_PAYMENTS_ENABLED=1 uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 &
```
Wait until it responds: `curl -fsS http://127.0.0.1:8000/health || curl -fsS http://127.0.0.1:8000/docs >/dev/null` (use whichever health path exists; the walkthrough's BASE default is `http://127.0.0.1:8000`).

- [ ] **Step 2: Run the narrated tour (TTY path).**

Run: `uv run python -m scripts.client_walkthrough`
Expected: exit 0; SUDO boots, narrates sections with face/bubble, reacts on OK/WARN, and signs off with `outro` showing `(N ok, M warn)`. The new `4b. System Integrity` section reports OK or a WARN (never FAIL on combat RNG).

- [ ] **Step 3: Run the CI/plain path.**

Run: `uv run python -m scripts.client_walkthrough --no-toon | head -40`
Expected: exit 0; NO face/bubble art; plain `OK/WARN/FAIL` lines exactly as before SUDO existed. (Also verify piping to a non-TTY auto-suppresses the toon even without `--no-toon`, since `sys.stdout.isatty()` is False when piped.)

- [ ] **Step 4: Stop the server.**

```bash
kill %1 2>/dev/null || true
```

- [ ] **Step 5: Final unit-test pass + commit.**

```bash
uv run pytest tests/test_sudo.py -v
git add -A
git commit -m "test(walkthrough): SUDO daemon live acceptance verified" --allow-empty
```

---

## Self-review notes

- **Spec coverage:** `scripts/sudo.py` with FACES + `speak()` (T1) + quip banks + `Sudo` narrator with enabled-gating (T2); integration via delegating helpers + `--no-toon` + TTY gating + outro (T3); System Integrity coverage section (T4); live acceptance + CI-plain verification (T5). `tests/test_sudo.py` covers `speak` wrap/render, all moods have faces, FAIL tombstone, disabled→plain contract, quip determinism (T1-2).
- **No new deps:** stdlib `textwrap`/`shutil`/`argparse` only.
- **CI-safe:** `Sudo(enabled=False)` (non-TTY or `--no-toon`) prints the exact pre-SUDO `OK/WARN/FAIL` lines; box-drawing/face art only when a TTY.
- **Type/name consistency:** `Mood` literals, `FACES`, `QUIPS`, `quip(bank, i)`, `speak(message, mood, *, width, color)`, and `Sudo(enabled=, color=, width=)` with methods `boot/section/ok/warn/fail/outro` are used identically across T1-T4.
- **Determinism:** pure `speak`/`quip(bank, i)` are deterministic for tests; the live narrator rotates a per-bank cursor by call order (still deterministic, no RNG).
- **Cross-task dependency:** T3 wires `tour_system_integrity` into `main()` and T4 defines it — flagged inline; subagent-driven order (T3 then T4) resolves it, and the `-c "import ..."` smoke in T3 still passes because the reference lives inside `async def main`, not at import time.
- **Out of scope (separate):** the 2 pre-existing frontend test failures.
