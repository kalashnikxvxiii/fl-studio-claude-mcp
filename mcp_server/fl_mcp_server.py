#!/usr/bin/env python3
"""FL Studio MCP server.

Bridges Claude (MCP) to an FL Studio MIDI controller script running under Wine.
Each tool: writes command.json (with a monotonic id), sends one MIDI note to the
virtual MIDI port FL listens on (firing the script's OnMidiMsg), then polls
result.json for the matching id.

Env overrides:
  FL_MCP_DIR    shared folder (Linux path to the controller-script dir)
  FL_MCP_MIDI   rawmidi device for the trigger note (default /dev/snd/midiC4D0)
"""
import json
import os
import time
import getpass

from mcp.server.fastmcp import FastMCP

try:
    from .format import (readable_project, pitch_name, ticks_to_beats,
                         build_import_payload, normalize_steps)
    from . import library as _lib
    from . import idgen as _idgen
    from . import preflight as _preflight
except ImportError:                # when run as a plain script, not a package
    from format import (readable_project, pitch_name, ticks_to_beats,
                        build_import_payload, normalize_steps)
    import library as _lib
    import idgen as _idgen
    import preflight as _preflight

USER = getpass.getuser()
DEFAULT_DIR = os.path.expanduser(
    "~/.local/share/wineprefixes/flstudio/drive_c/users/%s/"
    "Documents/Image-Line/FL Studio/Settings/Hardware/FLClaudeMCP" % USER
)
SHARED_DIR = os.environ.get("FL_MCP_DIR", DEFAULT_DIR)
MIDI_DEV = os.environ.get("FL_MCP_MIDI", "/dev/snd/midiC4D0")
CMD_PATH = os.path.join(SHARED_DIR, "command.json")
RES_PATH = os.path.join(SHARED_DIR, "result.json")
# The Export Notes piano-roll script can only write inside FL's "Piano roll scripts"
# folder (its sandbox blocks the Hardware dir), so notes_export.json lands there.
NOTES_DIR = os.environ.get(
    "FL_MCP_NOTES_DIR",
    os.path.join(os.path.dirname(os.path.dirname(SHARED_DIR.rstrip("/"))),
                 "Piano roll scripts"),
)
NOTES_PATH = os.path.join(NOTES_DIR, "notes_export.json")
NOTES_IMPORT_PATH = os.path.join(NOTES_DIR, "notes_import.json")

# Library roots inside the Wine prefix (override for tests via FL_MCP_LIB_ROOTS,
# os.pathsep-separated).
_PROG_DATA = os.path.expanduser(
    "~/.local/share/wineprefixes/flstudio/drive_c/Program Files/Image-Line/"
    "FL Studio 2025/Data")
_default_roots = os.pathsep.join([
    os.path.join(_PROG_DATA, "System", "Plugin databases"),
    os.path.join(_PROG_DATA, "Patches", "Plugin presets"),
    os.path.join(_PROG_DATA, "Patches", "Packs"),
])
LIB_ROOTS = os.environ.get("FL_MCP_LIB_ROOTS", _default_roots).split(os.pathsep)
LIB_CACHE = os.path.join(SHARED_DIR, "library_index.json")
ID_COUNTER = os.path.join(SHARED_DIR, "id_counter.txt")
FL_PROC = os.environ.get("FL_MCP_FL_PROC", "FL64.exe")

mcp = FastMCP("fl-studio")


class FLError(RuntimeError):
    pass


def _trigger_midi():
    """Write a note-on/off to the rawmidi device to fire FL's OnMidiMsg."""
    try:
        with open(MIDI_DEV, "wb", buffering=0) as f:
            f.write(bytes([0x90, 60, 100]))   # note on
            f.write(bytes([0x80, 60, 0]))     # note off
    except OSError as e:
        raise FLError("cannot write MIDI trigger to %s: %s "
                      "(is snd-virmidi loaded? are you in the 'audio' group?)"
                      % (MIDI_DEV, e))


def _send(op, args=None, timeout=4.0):
    """Send a command to FL and return its result (raises FLError on failure)."""
    cid = _idgen.next_id(ID_COUNTER)
    with open(CMD_PATH, "w") as f:
        json.dump({"id": cid, "op": op, "args": args or {}}, f)
    _trigger_midi()

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with open(RES_PATH, "r") as f:
                res = json.load(f)
        except (OSError, ValueError):
            res = None
        if res and res.get("id") == cid:
            if res.get("ok"):
                return res.get("result")
            raise FLError(res.get("error", "unknown FL error"))
        time.sleep(0.02)
    raise FLError(
        "timeout waiting for FL (is FL running with the FLClaudeMCP controller "
        "assigned to the virtual MIDI input?)")


# ---- tools ---------------------------------------------------------------------

@mcp.tool()
def fl_ping() -> dict:
    """Check the bridge: returns FL version, tempo, and play state."""
    return _send("ping")


@mcp.tool()
def fl_status() -> dict:
    """Pre-flight check: is the bridge ready? Diagnoses snd-virmidi, the FL process,
    and the controller, with a fix hint for whatever is missing. Call this first if
    commands time out."""
    def _ping():
        try:
            return _send("ping", timeout=1.5)
        except FLError:
            return None
    return _preflight.check_environment(MIDI_DEV, FL_PROC, _ping)


@mcp.tool()
def fl_get_project() -> dict:
    """Read the current FL project: context (tempo/ppq/pattern; key is null —
    ask the user), channels with per-step pitch/velocity, and mixer tracks with
    plugin names. Use this before composing."""
    return readable_project(_send("get_project"))


@mcp.tool()
def fl_get_state() -> dict:
    """Deprecated alias of fl_get_project (back-compat)."""
    return fl_get_project()


@mcp.tool()
def fl_read_notes() -> dict:
    """Read piano-roll notes exported by the 'Export Notes' piano-roll script.
    Workflow: in FL open the clip in the Piano Roll, run the script from the
    menu (hamburger) > Scripting > Export Notes, THEN call this. Returns notes
    with note-names and beat positions, or an instruction if no export is present."""
    try:
        with open(NOTES_PATH) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {"ok": False,
                "hint": "No notes_export.json. In FL: open the clip in the Piano "
                        "Roll, then menu > Scripting > Export Notes, then retry."}
    ppq = data.get("ppq", 384)
    notes = []
    for n in data.get("notes", []):
        notes.append({
            "note": pitch_name(n["pitch"]),
            "pitch": n["pitch"],
            "beat": ticks_to_beats(n.get("start", 0), ppq),
            "length_beats": ticks_to_beats(n.get("length", 0), ppq),
            "velocity": n.get("velocity"),
        })
    return {"ok": True, "ppq": ppq, "note_count": len(notes), "notes": notes}


@mcp.tool()
def fl_write_notes(notes: list, mode: str = "replace",
                   channel: int = None, pattern: int = None) -> dict:
    """Compose notes into an FL piano-roll clip. `notes` is a list of dicts with
    pitch (MIDI, 60=C5), start_beat, length_beats, velocity (0-127). mode='replace'
    rewrites the clip; mode='merge' adds, skipping exact duplicates.

    Hybrid: if `pattern`/`channel` are given, the controller pre-selects them so the
    user opens the right clip. The user must then open that clip's Piano Roll and run
    'Import Notes' (menu > Tools > Scripting). Returns the instruction to do so."""
    selected = {}
    if pattern is not None:
        selected["pattern"] = _send("pattern_select", {"index": int(pattern)})
    if channel is not None:
        selected["channel"] = _send("channel_select", {"index": int(channel)})

    payload = build_import_payload(notes, mode)
    try:
        with open(NOTES_IMPORT_PATH, "w") as f:
            json.dump(payload, f)
    except OSError as e:
        return {"ok": False, "error": "could not write notes_import.json: %s" % e}

    where = ""
    if "channel" in selected:
        cinfo = selected["channel"].get("result", selected["channel"])
        where = " on channel %s '%s'" % (cinfo.get("selected"), cinfo.get("name"))
    return {
        "ok": True,
        "wrote": len(payload["notes"]),
        "mode": payload["mode"],
        "selected": selected,
        "instruction": ("Open the target clip's Piano Roll%s and run "
                        "menu > Tools > Scripting > Import Notes." % where),
    }


@mcp.tool()
def fl_search_library(query: str, kind: str = None, plugin: str = None,
                      limit: int = 20, refresh: bool = False) -> dict:
    """Search FL's installed library (instruments, effects, presets, samples) by name,
    plugin, or category. kind filters to 'instrument'|'effect'|'preset'|'sample';
    plugin filters to a generator (e.g. 'Sytrus'). Returns candidate records with
    Windows-style paths. Use during composition to find/suggest sounds; loading them
    into FL is still manual."""
    index = _lib.load_or_build_index(LIB_CACHE, LIB_ROOTS, refresh=refresh)
    results = _lib.search(index, query, kind=kind, plugin=plugin, limit=limit)
    return {"ok": True, "query": query, "count": len(results), "results": results}


@mcp.tool()
def fl_play() -> dict:
    """Start playback."""
    return _send("play")


@mcp.tool()
def fl_stop() -> dict:
    """Stop playback."""
    return _send("stop")


@mcp.tool()
def fl_record() -> dict:
    """Toggle recording arm."""
    return _send("record")


@mcp.tool()
def fl_set_tempo(bpm: float) -> dict:
    """Set the project tempo in BPM."""
    return _send("set_tempo", {"bpm": bpm})


@mcp.tool()
def fl_mixer_set_volume(track: int, volume: float) -> dict:
    """Set a mixer track's volume (0.0-1.0+; 0.8 ~= 0 dB)."""
    return _send("mixer_set_volume", {"track": track, "volume": volume})


@mcp.tool()
def fl_mixer_set_pan(track: int, pan: float) -> dict:
    """Set a mixer track's pan (-1.0 left .. 1.0 right)."""
    return _send("mixer_set_pan", {"track": track, "pan": pan})


@mcp.tool()
def fl_mixer_mute(track: int) -> dict:
    """Toggle mute on a mixer track."""
    return _send("mixer_mute", {"track": track})


@mcp.tool()
def fl_mixer_solo(track: int) -> dict:
    """Toggle solo on a mixer track."""
    return _send("mixer_solo", {"track": track})


@mcp.tool()
def fl_channel_select(index: int) -> dict:
    """Select a single channel in the channel rack by index."""
    return _send("channel_select", {"index": index})


@mcp.tool()
def fl_pattern_select(index: int) -> dict:
    """Jump to a pattern by index."""
    return _send("pattern_select", {"index": index})


@mcp.tool()
def fl_set_steps(channel: int, steps: list, length: int = 16) -> dict:
    """Write a channel's step row. `steps` may be a simple on/off list
    [1,0,1,...] OR a rich list [{"pos":0,"pitch":60,"velocity":100}, ...] for
    per-step pitch/velocity (groove, ghost notes, accents). Clears `length`
    steps first, then writes."""
    rich = normalize_steps(steps)
    return _send("set_steps", {"channel": channel, "steps": rich, "length": length})


@mcp.tool()
def fl_clear_steps(channel: int, length: int = 16) -> dict:
    """Clear the first `length` steps of a channel's step row."""
    return _send("clear_steps", {"channel": channel, "length": length})


@mcp.tool()
def fl_get_steps(channel: int, length: int = 16) -> dict:
    """Read a channel's steps as a rich list [{pos,pitch,velocity}, ...]."""
    return _send("get_steps", {"channel": channel, "length": length})


@mcp.tool()
def fl_channel_set_volume(channel: int, volume: float) -> dict:
    """Set a channel-rack channel's volume (0.0-1.0). Distinct from mixer-track volume."""
    return _send("channel_set_volume", {"channel": channel, "volume": volume})


@mcp.tool()
def fl_channel_set_pan(channel: int, pan: float) -> dict:
    """Set a channel-rack channel's pan (-1.0 left .. 1.0 right)."""
    return _send("channel_set_pan", {"channel": channel, "pan": pan})


@mcp.tool()
def fl_channel_mute(channel: int) -> dict:
    """Toggle mute on a channel-rack channel."""
    return _send("channel_mute", {"channel": channel})


if __name__ == "__main__":
    mcp.run()
