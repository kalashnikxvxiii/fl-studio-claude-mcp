"""Pure FL-library indexing: classify .fst/.wav by PATH (no binary parsing),
scan the library roots, search, and cache the index. FL-independent."""
import json
import os


def _to_windows(path):
    """Best-effort Linux prefix path -> Windows-style for display in FL."""
    marker = "/drive_c/"
    if marker in path:
        tail = path.split(marker, 1)[1]
        return "C:\\" + tail.replace("/", "\\")
    return path


def _parts(path):
    return [p for p in path.replace("\\", "/").split("/") if p]


def classify_fst(path):
    """Classify a .fst by its location in the FL library tree."""
    parts = _parts(path)
    name = os.path.splitext(parts[-1])[0] if parts else ""
    rec = {"name": name, "kind": "preset", "plugin": None,
           "category": None, "path": _to_windows(path)}

    def after(token):
        for i, p in enumerate(parts):
            if p.lower() == token and i + 1 < len(parts):
                return parts[i + 1:]
        return None

    db = None
    for i, p in enumerate(parts):
        if p.lower().startswith("plugin database"):
            db = parts[i + 1:]
            break
    if db is not None:
        # .../Generators|Effects/<Category>/<Name>.fst  -> a raw plugin
        rec["kind"] = "effect" if (db and db[0].lower() == "effects") else "instrument"
        if len(db) >= 3:
            rec["category"] = db[1]
        return rec

    pp = after("plugin presets")
    if pp is not None:
        # Generators/<Instrument>/<SoundCategory...>/<Name>.fst
        gen = pp[1:] if pp and pp[0].lower() in ("generators", "effects") else pp
        if len(gen) >= 1:
            rec["plugin"] = gen[0]
        if len(gen) >= 3:
            rec["category"] = gen[1]
        rec["kind"] = "preset"
        return rec

    return rec


def classify_wav(path):
    parts = _parts(path)
    name = os.path.splitext(parts[-1])[0] if parts else ""
    category = parts[-2] if len(parts) >= 2 else None
    return {"name": name, "kind": "sample", "plugin": None,
            "category": category, "path": _to_windows(path)}
