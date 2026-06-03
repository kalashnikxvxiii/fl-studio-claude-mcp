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
    """Annotate a raw get_project dict with note names; pass any other keys through."""
    out = dict(raw)                       # carry through patterns/markers/etc.
    out["context"] = dict(raw.get("context", {}))
    out["mixer"] = raw.get("mixer", [])
    out["channels"] = []
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


def normalize_steps(steps):
    """Normalize the two accepted step forms into a rich list.

    Simple form: [1, 0, 1, ...] -> one entry per ON position, default pitch/velocity.
    Rich form:   [{pos, pitch?, velocity?}, ...] -> defaults filled, velocity clamped.
    Default pitch=60, velocity=100; velocity clamped to 0..127.
    """
    if not steps:
        return []
    out = []
    if isinstance(steps[0], dict):
        for s in steps:
            vel = max(0, min(127, int(s.get("velocity", 100))))
            out.append({"pos": int(s["pos"]),
                        "pitch": int(s.get("pitch", 60)),
                        "velocity": vel})
    else:
        for pos, on in enumerate(steps):
            if on:
                out.append({"pos": pos, "pitch": 60, "velocity": 100})
    return out


def color_to_int(spec):
    """Color spec -> FL int (0xRRGGBB). Accepts '#RRGGBB', 'RRGGBB', or [r,g,b].
    Invalid input -> 0 (never raises)."""
    try:
        if isinstance(spec, (list, tuple)) and len(spec) == 3:
            r, g, b = (int(spec[0]), int(spec[1]), int(spec[2]))
            return (r << 16) | (g << 8) | b
        if isinstance(spec, str):
            return int(spec.lstrip("#"), 16)
    except (ValueError, TypeError):
        return 0
    return 0


def int_to_hex(value):
    """FL color int -> '#RRGGBB' (masks the sign bit FL returns)."""
    try:
        return "#%06X" % (int(value) & 0xFFFFFF)
    except (ValueError, TypeError):
        return "#000000"
