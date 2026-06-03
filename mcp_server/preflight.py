"""Pre-flight environment diagnosis for the FL bridge. The live ping is injected so the
filesystem/process checks are unit-testable without FL."""
import os
import subprocess


def _default_midi_exists(path):
    return os.path.exists(path)


def _default_proc_running(name):
    try:
        return subprocess.run(["pgrep", "-x", name],
                              capture_output=True).returncode == 0
    except OSError:
        return False


def check_environment(midi_dev, fl_proc, ping_fn,
                      _midi_exists=_default_midi_exists,
                      _proc_running=_default_proc_running):
    """Diagnose bottom-up: virmidi device, FL process, controller ping.
    ping_fn() returns the ping result dict, or None on timeout/no-response.
    Returns {ready, checks:[{name, ok, hint}], hint}."""
    checks = []

    midi_ok = _midi_exists(midi_dev)
    checks.append({"name": "virmidi", "ok": midi_ok,
                   "hint": "" if midi_ok else
                   "snd-virmidi not loaded -> run: sudo modprobe snd-virmidi"})
    if not midi_ok:
        return {"ready": False, "checks": checks, "hint": checks[-1]["hint"]}

    fl_ok = _proc_running(fl_proc)
    checks.append({"name": "fl_running", "ok": fl_ok,
                   "hint": "" if fl_ok else
                   "FL Studio not running -> launch it (e.g. `flstudio`)"})
    if not fl_ok:
        return {"ready": False, "checks": checks, "hint": checks[-1]["hint"]}

    ping = None
    try:
        ping = ping_fn()
    except Exception:
        ping = None
    ctrl_ok = ping is not None
    checks.append({"name": "controller", "ok": ctrl_ok,
                   "hint": "" if ctrl_ok else
                   "FL up but controller not responding -> in FL: MIDI settings "
                   "> Controller type > FLClaudeMCP"})
    if not ctrl_ok:
        return {"ready": False, "checks": checks, "hint": checks[-1]["hint"]}

    hint = "ready (FL v%s, tempo %s)" % (ping.get("version"), ping.get("tempo"))
    return {"ready": True, "checks": checks, "hint": hint}
