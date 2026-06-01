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
    from .format import readable_project, pitch_name, ticks_to_beats
except ImportError:                # when run as a plain script, not a package
    from format import readable_project, pitch_name, ticks_to_beats

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

_next_id = int(time.time())  # unlikely to collide with a stale result file

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
    global _next_id
    _next_id += 1
    cid = _next_id
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
def fl_set_steps(channel: int, steps: list[int]) -> dict:
    """Write a step-sequencer row for a channel. `steps` is a list of 0/1
    (e.g. a 16-step kick: [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0])."""
    return _send("set_steps", {"channel": channel, "steps": steps})


@mcp.tool()
def fl_clear_steps(channel: int, length: int = 16) -> dict:
    """Clear the first `length` steps of a channel's step row."""
    return _send("clear_steps", {"channel": channel, "length": length})


@mcp.tool()
def fl_get_steps(channel: int, length: int = 16) -> dict:
    """Read the first `length` steps of a channel's step row."""
    return _send("get_steps", {"channel": channel, "length": length})


if __name__ == "__main__":
    mcp.run()
