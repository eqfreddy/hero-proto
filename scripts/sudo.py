"""SUDO -- a deadpan helpdesk daemon that narrates the client walkthrough.

Pure, stdlib-only, no server knowledge. `speak()` returns a string (prints
nothing) so it is trivially testable; the `Sudo` narrator handles state,
gating, and printing.
"""

from __future__ import annotations

import shutil
import textwrap
from typing import Literal

Mood = Literal["BOOT", "NEUTRAL", "OK", "WARN", "FAIL", "DONE"]

# ASCII faces. Each non-FAIL face shares the "[ SUDO ]" framing; FAIL is a
# tombstone (the tour dies on first failure). The tests key on FACES being
# present + non-empty for every Mood and on "R.I.P" living in FAIL.
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
    # Preserve explicit newlines; wrap each paragraph to width.
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


# Deadpan, faux-corporate register. Banks are indexed (not random) so the live
# tour varies lines by call order while tests stay deterministic.
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

    When `enabled` is False, methods print only the plain ``PREFIX message``
    line (identical machine-readable contract to the pre-SUDO script). When
    enabled, each prints SUDO's face + bubble (a quip) followed by the line.
    Tracks pass/warn counts for the outro and rotates quip cursors by call
    order (deterministic -- no RNG).
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
