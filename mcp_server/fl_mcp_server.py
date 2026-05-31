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

USER = getpass.getuser()
DEFAULT_DIR = os.path.expanduser(
    "~/.local/share/wineprefixes/flstudio/drive_c/users/%s/"
    "Documents/Image-Line/FL Studio/Settings/Hardware/FLClaudeMCP" % USER
)
SHARED_DIR = os.environ.get("FL_MCP_DIR", DEFAULT_DIR)
MIDI_DEV = os.environ.get("FL_MCP_MIDI", "/dev/snd/midiC4D0")
CMD_PATH = os.path.join(SHARED_DIR, "command.json")
RES_PATH = os.path.join(SHARED_DIR, "result.json")

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
def fl_get_state() -> dict:
    """Full snapshot: version, tempo, transport, pattern, mixer tracks, channels."""
    return _send("get_state")


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


if __name__ == "__main__":
    mcp.run()
