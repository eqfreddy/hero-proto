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
