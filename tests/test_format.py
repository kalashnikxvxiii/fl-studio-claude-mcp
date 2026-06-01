from mcp_server.format import pitch_name, ticks_to_beats, readable_project


def test_pitch_name_middle_c():
    assert pitch_name(60) == "C5"          # FL convention: C5 = MIDI 60
    assert pitch_name(61) == "C#5"
    assert pitch_name(57) == "A4"


def test_ticks_to_beats():
    assert ticks_to_beats(384, 384) == 1.0
    assert ticks_to_beats(192, 384) == 0.5
    assert ticks_to_beats(0, 384) == 0.0


def test_readable_project_adds_note_names_and_beats():
    raw = {
        "context": {"tempo": 126.0, "ppq": 384, "pattern": 1, "key": None},
        "channels": [
            {"index": 0, "name": "Kick", "plugin": None, "step_count": 16,
             "steps": [{"pos": 0, "pitch": 60, "velocity": 100}]},
        ],
        "mixer": [],
    }
    out = readable_project(raw)
    ch = out["channels"][0]
    assert ch["steps"][0]["note"] == "C5"
    assert out["context"]["tempo"] == 126.0
