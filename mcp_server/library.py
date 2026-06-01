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

    # A "Plugin database (...)" leaf folder holds: <Generators|Effects>/<Category>/<Name>.fst
    db = None
    for i, p in enumerate(parts):
        pl = p.lower()
        if pl.startswith("plugin database") and pl != "plugin databases":
            db = parts[i + 1:]
            break
    if db is not None:
        # db = [Generators|Effects, <Category>, <Name>.fst]
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


def scan_library(roots):
    """Walk roots, classify every .fst/.wav, return a list of records."""
    index = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for fn in files:
                low = fn.lower()
                full = os.path.join(dirpath, fn)
                if low.endswith(".fst"):
                    index.append(classify_fst(full))
                elif low.endswith(".wav"):
                    index.append(classify_wav(full))
    return index


def _score(rec, q):
    if not q:
        return 1
    name = (rec.get("name") or "").lower()
    plugin = (rec.get("plugin") or "").lower()
    cat = (rec.get("category") or "").lower()
    if name == q:
        return 100
    if q in name:
        return 60
    if q in plugin:
        return 40
    if q in cat:
        return 20
    return 0


def search(index, query, kind=None, plugin=None, limit=20):
    q = (query or "").strip().lower()
    out = []
    for rec in index:
        if kind and rec.get("kind") != kind:
            continue
        if plugin and (rec.get("plugin") or "").lower() != plugin.lower():
            continue
        sc = _score(rec, q)
        if q and sc == 0:
            continue
        out.append((sc, rec))
    out.sort(key=lambda t: (-t[0], t[1].get("name") or ""))
    return [r for _s, r in out[:limit]]


def load_or_build_index(cache_path, roots, refresh=False):
    """Return the index from cache if present (and not refresh), else scan + cache."""
    if not refresh:
        try:
            with open(cache_path) as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    index = scan_library(roots)
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(index, f)
    except OSError:
        pass
    return index
