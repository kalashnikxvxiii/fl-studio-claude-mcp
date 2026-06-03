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


from mcp_server.format import beats_to_ticks, build_import_payload


def test_beats_to_ticks():
    assert beats_to_ticks(1.0, 96) == 96
    assert beats_to_ticks(0.5, 96) == 48
    assert beats_to_ticks(0.0, 384) == 0
    assert beats_to_ticks(2.5, 96) == 240


def test_build_import_payload_defaults_replace():
    notes = [{"pitch": 60, "start_beat": 0.0, "length_beats": 0.5, "velocity": 100}]
    p = build_import_payload(notes)
    assert p["mode"] == "replace"
    assert p["notes"] == notes


def test_build_import_payload_merge_and_normalizes():
    notes = [{"pitch": 64, "start_beat": 1, "length_beats": 1}]  # no velocity
    p = build_import_payload(notes, mode="merge")
    assert p["mode"] == "merge"
    assert p["notes"][0]["velocity"] == 100          # default filled
    assert p["notes"][0]["start_beat"] == 1.0        # coerced to float


def test_build_import_payload_rejects_bad_mode():
    p = build_import_payload([], mode="nonsense")
    assert p["mode"] == "replace"                    # unknown -> replace


from mcp_server.format import normalize_steps


def test_normalize_steps_simple_form():
    out = normalize_steps([1, 0, 1, 0])
    assert out == [
        {"pos": 0, "pitch": 60, "velocity": 100},
        {"pos": 2, "pitch": 60, "velocity": 100},
    ]


def test_normalize_steps_rich_form_fills_defaults():
    out = normalize_steps([{"pos": 0, "pitch": 64, "velocity": 70}, {"pos": 4}])
    assert out[0] == {"pos": 0, "pitch": 64, "velocity": 70}
    assert out[1] == {"pos": 4, "pitch": 60, "velocity": 100}


def test_normalize_steps_clamps_velocity():
    out = normalize_steps([{"pos": 0, "velocity": 200}, {"pos": 1, "velocity": -5}])
    assert out[0]["velocity"] == 127
    assert out[1]["velocity"] == 0


def test_normalize_steps_empty():
    assert normalize_steps([]) == []
