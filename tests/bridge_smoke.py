#!/usr/bin/env python3
"""Standalone smoke test for the FL bridge (no MCP needed).

Writes command.json, fires a MIDI trigger to the virmidi device, and reads
result.json — exactly what the MCP server does. Run a few read-only ops.

Usage: python3 tests/bridge_smoke.py
"""
import json
import os
import sys
import time
import getpass

USER = getpass.getuser()
DIR = os.environ.get("FL_MCP_DIR", os.path.expanduser(
    "~/.local/share/wineprefixes/flstudio/drive_c/users/%s/"
    "Documents/Image-Line/FL Studio/Settings/Hardware/FLClaudeMCP" % USER))
MIDI = os.environ.get("FL_MCP_MIDI", "/dev/snd/midiC4D0")
CMD = os.path.join(DIR, "command.json")
RES = os.path.join(DIR, "result.json")

_id = int(time.time())


def send(op, args=None, timeout=4.0):
    global _id
    _id += 1
    cid = _id
    with open(CMD, "w") as f:
        json.dump({"id": cid, "op": op, "args": args or {}}, f)
    with open(MIDI, "wb", buffering=0) as f:
        f.write(bytes([0x90, 60, 100]))
        f.write(bytes([0x80, 60, 0]))
    end = time.time() + timeout
    while time.time() < end:
        try:
            with open(RES) as f:
                r = json.load(f)
            if r.get("id") == cid:
                return r
        except (OSError, ValueError):
            pass
        time.sleep(0.02)
    return {"id": cid, "ok": False, "error": "TIMEOUT (FL running? controller assigned?)"}


def main():
    print("dir :", DIR)
    print("midi:", MIDI)
    if not os.path.isdir(DIR):
        print("!! controller folder not found"); sys.exit(1)
    if not os.path.exists(MIDI):
        print("!! %s missing — load snd-virmidi (sudo modprobe snd-virmidi)" % MIDI); sys.exit(1)
    for op, args in [("ping", None), ("get_state", None)]:
        print("\n>>> %s %s" % (op, args or ""))
        print(json.dumps(send(op, args), indent=2)[:1200])


if __name__ == "__main__":
    main()
