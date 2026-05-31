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
    # The OK face's second line appears in the rendered block.
    assert sudo.FACES["OK"].splitlines()[1] in out


def test_speak_wraps_long_messages_to_width():
    long = "diagnostics " * 20  # ~240 chars, no natural short lines
    out = sudo.speak(long, width=30, color=False)
    for line in out.splitlines():
        assert len(line) <= 50, f"line too wide ({len(line)}): {line!r}"
    assert out.count("diagnostics") == 20


def test_speak_handles_multiline_without_overflow():
    out = sudo.speak("line one\nline two that is a bit longer", width=40, color=False)
    assert "line one" in out and "line two that is a bit longer" in out


def test_quip_is_deterministic_and_wraps_index():
    bank = "section"
    first = sudo.quip(bank, 0)
    assert first == sudo.quip(bank, 0)                      # deterministic
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
    assert "+---------+" not in out      # no face art when disabled
    assert "[ SUDO ]" not in out
    assert "OK stage cleared" in out     # plain machine-readable lines survive
    assert "WARN no crash reached" in out


def test_enabled_narrator_renders_face(capsys):
    s = sudo.Sudo(enabled=True, color=False)
    s.ok("stage cleared")
    out = capsys.readouterr().out
    assert "[ SUDO ]" in out
    assert "stage cleared" in out


def test_fail_raises_system_exit(capsys):
    import pytest
    s = sudo.Sudo(enabled=False, color=False)
    with pytest.raises(SystemExit):
        s.fail("register failed")
    assert "FAIL register failed" in capsys.readouterr().out
