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
