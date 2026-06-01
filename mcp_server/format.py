"""Pure formatting helpers (no FL dependency) — unit-tested."""

_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def pitch_name(midi_pitch):
    """MIDI pitch -> FL-convention note name (C5 == MIDI 60).

    FL labels middle C (MIDI 60) as C5, so the octave digit is ``pitch // 12``
    (60 -> 5, 57 -> 4, 72 -> 6).
    """
    return "%s%d" % (_NOTES[midi_pitch % 12], midi_pitch // 12)


def ticks_to_beats(ticks, ppq):
    if not ppq:
        return 0.0
    return ticks / ppq


def readable_project(raw):
    """Annotate a raw get_project dict with note names; pass-through otherwise."""
    out = {"context": dict(raw.get("context", {})),
           "channels": [], "mixer": raw.get("mixer", [])}
    for ch in raw.get("channels", []):
        c = dict(ch)
        c["steps"] = []
        for st in ch.get("steps", []):
            s = dict(st)
            if "pitch" in s:
                s["note"] = pitch_name(s["pitch"])
            c["steps"].append(s)
        out["channels"].append(c)
    return out


def beats_to_ticks(beats, ppq):
    """Beats (quarter notes) -> integer ticks at the given PPQ."""
    return int(round(beats * ppq))


def build_import_payload(notes, mode="replace"):
    """Validate/normalize note dicts into the notes_import.json payload.

    Each note: pitch (int), start_beat (float), length_beats (float),
    velocity (0..127, default 100). Unknown mode -> 'replace'.
    """
    if mode not in ("replace", "merge"):
        mode = "replace"
    norm = []
    for n in notes:
        norm.append({
            "pitch": int(n["pitch"]),
            "start_beat": float(n["start_beat"]),
            "length_beats": float(n["length_beats"]),
            "velocity": int(n.get("velocity", 100)),
        })
    return {"mode": mode, "notes": norm}
