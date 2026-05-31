# SUDO — the walkthrough daemon (terminal mascot) Design

**Date:** 2026-05-31
**Status:** Approved (design), ready for implementation plan.
**Scope:** Terminal mascot for `scripts/client_walkthrough.py` (CLI acceptance tour). The in-app player-onboarding mascot is a deferred follow-up (not this spec).

## Purpose

`scripts/client_walkthrough.py` is the "run it before shipping a build" acceptance tour — a fresh account exercises every player-facing feature against a live server, printing `OK`/`WARN`/`FAIL` and exiting on the first failure. This adds **SUDO, a deadpan helpdesk daemon** that narrates the tour: a cold, omniscient, faux-corporate ASCII character that reacts to results with mood states. It also folds in a coverage gap (the new System Integrity combat) so the tour reflects what ships today.

Brand voice: dry, deadpan, robotic-corporate. "permission granted. reluctantly."

## Research basis

The canonical terminal-mascot pattern is **cowsay** (ASCII character + speech bubble). The one real gotcha: long messages overflow the bubble unless wrapped to terminal width. We implement a stdlib cowsay-style renderer (no `rich`/`cowsay` dependency — the project avoids non-essential deps and the script already does raw ANSI + forced UTF-8). Sources: <https://itsfoss.com/cowsay/>, <https://hermes-agent.nousresearch.com/docs/user-guide/skills/bundled/creative/creative-ascii-art>.

## Architecture

Two units, clear boundary:

1. **`scripts/sudo.py`** — the daemon. Pure, stdlib-only, independently testable. Knows nothing about the walkthrough; it just renders SUDO and holds the quip banks.
2. **`scripts/client_walkthrough.py`** — the tour. Imports `sudo`, calls it at boot / per-section / per-result / outro. Owns all server interaction (unchanged responsibility).

### `scripts/sudo.py` interface

```python
# Moods drive both the face and the default voice register.
Mood = Literal["BOOT", "NEUTRAL", "OK", "WARN", "FAIL", "DONE"]

FACES: dict[Mood, str]          # ASCII art per mood; FAIL == tombstone

def speak(message: str, mood: Mood = "NEUTRAL", *, width: int | None = None,
          color: bool = True) -> str:
    """Return SUDO's face + a cowsay-style speech bubble containing `message`,
    word-wrapped to `width` (default: min(terminal width, 60), floor 24).
    Pure — returns a string, prints nothing."""

# Deterministic-by-default quip access (stable for tests); callers may pass an
# index/rng for variety in the live tour.
SECTION_QUIPS: list[str]
def quip(bank: str, i: int = 0) -> str: ...   # bank in {"boot","section","ok","warn","fail","done"}

class Sudo:
    """Stateful narrator used by the walkthrough. Tracks enabled-ness and a
    rotating quip cursor so the live tour varies lines without randomness."""
    def __init__(self, *, enabled: bool, color: bool, width: int | None = None): ...
    def boot(self) -> None: ...
    def section(self, title: str) -> None: ...
    def ok(self, msg: str) -> None: ...      # mood OK
    def warn(self, msg: str) -> None: ...     # mood WARN
    def fail(self, msg: str) -> None: ...     # mood FAIL (tombstone)
    def outro(self, passed: int, warned: int) -> None: ...
    # When `enabled` is False, methods emit the plain prefixed line only
    # (no face/bubble) — identical machine-readable output to today.
```

- **Wrapping:** `speak` wraps the message body to the computed width and frames it in a `+--…--+` bubble with a `\`-tail pointing at the face, cowsay-style. Multi-line messages handled (the documented cowsay failure mode).
- **`enabled` gating:** the walkthrough constructs `Sudo(enabled = sys.stdout.isatty() and not args.no_toon, color = sys.stdout.isatty())`. Non-TTY (CI) or `--no-toon` → plain `OK/WARN/FAIL` lines exactly as today; the face/bubble are suppressed. This keeps CI logs clean and the acceptance contract intact.
- **No randomness in the module's pure functions** (`speak`, `quip` with explicit index) so tests are deterministic. The `Sudo` instance rotates a cursor (`i % len(bank)`) for line variety — still deterministic given call order.

### Faces (mood states)

ASCII art (stdlib string constants), ~5-7 lines each, consistent `[ SUDO ]` framing:
- `BOOT` — daemon spinning up.
- `NEUTRAL` — default, between sections.
- `OK` — faint approval.
- `WARN` — a flicker of concern.
- `FAIL` — tombstone (`R.I.P`), since the tour dies on first failure.
- `DONE` — sign-off.

### Integration points in `client_walkthrough.py`

- **Boot:** `sudo.boot()` before the first request — announces the audit.
- **Per section** (~17): `sudo.section(title)` — a deadpan intro line. Existing section print stays.
- **Results:** the existing `_ok/_warn/_fail` helpers route through the `Sudo` instance so each carries a mood + occasional quip. `_fail` shows the tombstone, then the existing exit(1).
- **Outro:** on full pass, `sudo.outro(passed, warned)` — grudging "permission granted," with counts.
- **New coverage:** add a section that exercises the **System Integrity combat** — start an interactive battle, drive an enemy to Crashed, and confirm a `valid_delete_targets` entry + a successful `action_type="delete"` (the Plan-2/3a feature). `OK` if the delete resolves; `WARN` if no crash reached within the wave (don't hard-fail on combat RNG).

## Testing

`tests/test_sudo.py` (stdlib + pytest, no server):
- `speak` returns a string containing the face and the message; long messages wrap to ≤ width; a multi-line message renders without overflow.
- Every `Mood` has a face in `FACES`; `FAIL` face contains a tombstone marker (e.g. `RIP`).
- `Sudo(enabled=False)` emits plain prefixed lines with no box-drawing characters (CI-safe output identical to today's contract).
- `quip(bank, i)` is deterministic and bounds-safe (`i` wraps).

The walkthrough itself remains a live-server acceptance script (not unit-tested), as today.

## Non-goals / deferred

- In-app (React) player-onboarding mascot — separate future spec.
- Animation / live-redraw — static frames only.
- No new runtime dependencies.

## Out of scope (handled separately)

The two pre-existing frontend test failures (`dioramaLoader.test.ts`, `Guild/Raids.test.tsx`) are unrelated debugging, fixed outside this spec.
