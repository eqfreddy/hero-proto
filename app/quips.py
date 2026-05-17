"""Per-template signature quip lines. Fired once per battle on a hero's
first action so each operative feels like a person, not a statline.

Keyed by exact `HeroTemplate.name` (display name). Heroes not in this
table simply don't quip — the combat resolver silently skips emission.

Voice: dry, deadpan, occasionally morbid. Six-words-max so the quip
fits the floating-text style and reads in the time the attack clip plays.
"""

from __future__ import annotations

QUIPS: dict[str, str] = {
    "Ticket Gremlin":          "ack!",
    "Printer Whisperer":       "PC LOAD LETTER.",
    "Overnight Janitor":       "wet floor.",
    "Jaded Intern":            "sure, whatever.",
    "SRE on Call":             "paging incident commander.",
    "Compliance Officer":      "section 4.2.1, sir.",
    "Security Auditor":        "this fails SOC2.",
    "The Sysadmin":            "sudo !!",
    "Root-Access Janitor":     "rm -rf /tmp/you",
    "VP of Vibes":             "love the energy.",
    "Keymaster (Gary)":        "I AM the Keymaster.",
    "The Post-Mortem":         "no blame, just lessons.",
    "Midnight Pager":          "3 a.m. again.",
    "The Consultant":          "let's circle back.",
    "The Founder":             "we move fast.",
    "DevOps Apprentice":       "uh, git push?",
    "Forgotten Contractor":    "still on payroll?",
    "Helpdesk Veteran":        "have you tried rebooting?",
    "Build Engineer":          "green pipeline.",
    "Rogue DBA":                "DROP table enemies;",
    "Oncall Warrior":          "holding the pager.",
    "Retired Mainframe Guru":  "back in '78...",
    "Shadow IT Operator":      "off the books.",
    "The Whistleblower":       "git blame!",
    "The Successor":           "the throne is mine.",
    "Chaos Monkey":            "*chittering*",
    "Database Archaeologist":  "ancient indexes.",
    "Frontline L1 Tech":       "ticket escalated.",
    "Cert Collector":          "another badge.",
    "Tape Library Ghost":      "REW. PLAY. REW.",
    "Office Coffee Hoarder":   "this pot's mine.",
    "Blue Team Lead":          "containment phase.",
    "Agile Coach":              "stand-up time.",
    "On-Call Martyr":          "I got it.",
    "The Board Member":        "shareholder value.",
    "Applecrumb":              "crumbs everywhere.",
    "TBFAM":                   "to be fair, actually,",
    "The Man The Dev":         "ship it.",
}


def quip_for(name: str) -> str | None:
    """Return the quip line for this template name, or None if it has none."""
    return QUIPS.get(name)
