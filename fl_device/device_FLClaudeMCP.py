# name=FLClaudeMCP
# FL Studio MIDI Controller script — executor for the Claude MCP bridge.
#
# How it works: the MCP server (on Linux) writes a command to command.json and sends
# ONE MIDI note to the virtual MIDI port this controller is bound to. That fires
# OnMidiMsg(), from which the FULL FL controller API is available. We read the command,
# dispatch it, and write result.json. The MCP server polls result.json for the result.
#
# OnMidiMsg fires several times per note, so each command carries a monotonic `id` and
# we execute it only when the id is new.

import json

import general
import transport
import mixer
import channels
import patterns
import ui
import midi

# Folder of THIS script (Wine path). command.json / result.json live here.
# Keep in sync with the MCP server's resolved Linux path to the same folder.
_DIR = r"C:\users\kalashnikxv\Documents\Image-Line\FL Studio\Settings\Hardware\FLClaudeMCP"
_CMD = _DIR + r"\command.json"
_RES = _DIR + r"\result.json"

_last_id = -1


def _read_command():
    try:
        with open(_CMD, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _write_result(obj):
    try:
        with open(_RES, "w") as f:
            json.dump(obj, f)
    except Exception:
        pass


# ---- operations -----------------------------------------------------------------
# Each op: (args_dict) -> json-serializable result. Raise on error.

def op_ping(a):
    return {
        "version": general.getVersion(),
        "playing": bool(transport.isPlaying()),
        "tempo": mixer.getCurrentTempo() / 1000.0,
    }


def op_get_state(a):
    tracks = []
    for i in range(mixer.trackCount()):
        tracks.append({
            "index": i,
            "name": mixer.getTrackName(i),
            "volume": mixer.getTrackVolume(i),
            "pan": mixer.getTrackPan(i),
            "muted": bool(mixer.isTrackMuted(i)),
        })
    chans = [{"index": i, "name": channels.getChannelName(i)}
             for i in range(channels.channelCount())]
    return {
        "version": general.getVersion(),
        "tempo": mixer.getCurrentTempo() / 1000.0,
        "playing": bool(transport.isPlaying()),
        "recording": bool(transport.isRecording()),
        "pattern": patterns.patternNumber(),
        "mixer_tracks": tracks,
        "channels": chans,
    }


def op_play(a):
    if not transport.isPlaying():
        transport.start()
    return {"playing": True}


def op_stop(a):
    transport.stop()
    return {"playing": False}


def op_record(a):
    transport.record()
    return {"recording": bool(transport.isRecording())}


def op_set_tempo(a):
    bpm = float(a["bpm"])
    general.processRECEvent(
        midi.REC_Tempo, int(bpm * 1000),
        midi.REC_Control | midi.REC_UpdateControl | midi.REC_UpdatePlugLabel)
    return {"tempo": mixer.getCurrentTempo() / 1000.0}


def op_mixer_set_volume(a):
    t = int(a["track"]); v = float(a["volume"])
    mixer.setTrackVolume(t, v)
    return {"track": t, "volume": mixer.getTrackVolume(t)}


def op_mixer_set_pan(a):
    t = int(a["track"]); p = float(a["pan"])
    mixer.setTrackPan(t, p)
    return {"track": t, "pan": mixer.getTrackPan(t)}


def op_mixer_mute(a):
    t = int(a["track"])
    mixer.muteTrack(t)
    return {"track": t, "muted": bool(mixer.isTrackMuted(t))}


def op_mixer_solo(a):
    t = int(a["track"])
    mixer.soloTrack(t)
    return {"track": t}


def op_channel_select(a):
    i = int(a["index"])
    channels.selectOneChannel(i)
    return {"selected": i, "name": channels.getChannelName(i)}


def op_pattern_select(a):
    n = int(a["index"])
    patterns.jumpToPattern(n)
    return {"pattern": patterns.patternNumber()}


def op_set_steps(a):
    """Write a step row. `steps` is a normalized rich list [{pos,pitch,velocity}].
    Clears `length` (default 16) first, then writes each step's grid bit + params via
    setStepParameterByIndex(step, patNum, chanIndex, paramType, value, globalIndex)."""
    ch = int(a["channel"])
    steps = a["steps"]
    length = int(a.get("length", 16))
    channels.selectOneChannel(ch)
    pat = patterns.patternNumber()
    for pos in range(length):
        channels.setGridBit(ch, pos, 0)
    for s in steps:
        pos = int(s["pos"])
        channels.setGridBit(ch, pos, 1)
        # setStepParameterByIndex(index=channel, patNum, step, param, value)
        try:
            channels.setStepParameterByIndex(
                ch, pat, pos, STEP_PITCH, int(s.get("pitch", 60)))
            channels.setStepParameterByIndex(
                ch, pat, pos, STEP_VEL, int(s.get("velocity", 100)))
        except Exception:
            pass
    return {"channel": ch, "channel_name": channels.getChannelName(ch),
            "written": len(steps)}


def op_clear_steps(a):
    ch = int(a["channel"])
    length = int(a.get("length", 16))
    for pos in range(length):
        channels.setGridBit(ch, pos, 0)
    return {"channel": ch, "cleared": length}


def op_get_steps(a):
    ch = int(a["channel"])
    length = int(a.get("length", 16))
    return {"channel": ch, "channel_name": channels.getChannelName(ch),
            "steps": _channel_steps(ch, length)}


# Step parameter ids (confirmed live via probe: midi.pPitch=0, midi.pVelocity=1).
STEP_PITCH = midi.pPitch        # 0
STEP_VEL = midi.pVelocity       # 1
_GRID_LEN_DEFAULT = 16
_GRID_LEN_CAP = 64


def _channel_grid_len(ch):
    """Best-effort step-grid length: scan for the last ON/used step, round up to a
    multiple of 16 (min 16). getGridBit takes (channel, pos)."""
    try:
        last = -1
        for pos in range(_GRID_LEN_CAP):
            if channels.getGridBit(ch, pos):
                last = pos
        return max(((last // 16) + 1) * 16, _GRID_LEN_DEFAULT)
    except Exception:
        return _GRID_LEN_DEFAULT


def _channel_steps(ch, length):
    """ON steps of `ch` with pitch+velocity.
    getStepParam(step, param, index=channel, startPos)."""
    steps = []
    for pos in range(length):
        try:
            if not channels.getGridBit(ch, pos):
                continue
        except Exception:
            continue
        entry = {"pos": pos}
        try:
            entry["pitch"] = int(channels.getStepParam(pos, STEP_PITCH, ch, 0))
        except Exception:
            pass
        try:
            entry["velocity"] = int(channels.getStepParam(pos, STEP_VEL, ch, 0))
        except Exception:
            pass
        steps.append(entry)
    return steps


def _channel_plugin_name(ch):
    try:
        import plugins
        if plugins.isValid(ch, -1):
            return plugins.getPluginName(ch, -1, 0)
    except Exception:
        pass
    return None


def op_get_project(a):
    import general
    ctx = {
        "version": general.getVersion(),
        "tempo": mixer.getCurrentTempo() / 1000.0,
        "ppq": general.getRecPPB(),
        "playing": bool(transport.isPlaying()),
        "recording": bool(transport.isRecording()),
        "pattern": patterns.patternNumber(),
        "pattern_count": patterns.patternCount(),
        "key": None,  # controller API does not expose key/scale
    }
    try:
        ctx["pattern_name"] = patterns.getPatternName(patterns.patternNumber())
    except Exception:
        ctx["pattern_name"] = None

    chans = []
    for ch in range(channels.channelCount()):
        length = _channel_grid_len(ch)
        entry = {
            "index": ch,
            "name": channels.getChannelName(ch),
            "plugin": _channel_plugin_name(ch),
            "step_count": length,
            "steps": _channel_steps(ch, length),
        }
        try:
            entry["type"] = channels.getChannelType(ch)
        except Exception:
            entry["type"] = None
        try:
            entry["mixer_track"] = channels.getTargetFxTrack(ch)
        except Exception:
            entry["mixer_track"] = None
        chans.append(entry)

    try:
        import plugins
    except Exception:
        plugins = None
    tracks = []
    for i in range(mixer.trackCount()):
        slots = []
        if plugins is not None:
            for s in range(10):
                try:
                    slots.append(plugins.getPluginName(i, s, 0)
                                 if plugins.isValid(i, s) else None)
                except Exception:
                    slots.append(None)
        tracks.append({
            "index": i,
            "name": mixer.getTrackName(i),
            "volume": mixer.getTrackVolume(i),
            "pan": mixer.getTrackPan(i),
            "muted": bool(mixer.isTrackMuted(i)),
            "plugins": [p for p in slots if p],
        })

    pats = []
    try:
        for n in range(1, patterns.patternCount() + 1):
            p = {"num": n}
            try:
                p["name"] = patterns.getPatternName(n)
            except Exception:
                p["name"] = None
            try:
                p["color"] = _col_to_hex(patterns.getPatternColor(n))
            except Exception:
                p["color"] = None
            try:
                p["length"] = patterns.getPatternLength(n)
            except Exception:
                p["length"] = None
            pats.append(p)
    except Exception:
        pass

    try:
        marks = _scan_markers()
    except Exception:
        marks = []

    return {"context": ctx, "channels": chans, "mixer": tracks,
            "patterns": pats, "markers": marks}



def _col_to_hex(v):
    try:
        return "#%06X" % (int(v) & 0xFFFFFF)
    except Exception:
        return "#000000"


def op_pattern_rename(a):
    n = int(a["num"]); name = str(a["name"])
    patterns.setPatternName(n, name)
    return {"num": n, "name": patterns.getPatternName(n)}


def op_pattern_set_color(a):
    n = int(a["num"]); c = int(a["color_int"])
    patterns.setPatternColor(n, c)
    return {"num": n, "color": _col_to_hex(patterns.getPatternColor(n))}


def op_pattern_clone(a):
    n = int(a["num"])
    patterns.jumpToPattern(n)
    patterns.clonePattern(n)
    return {"cloned_from": n, "pattern_count": patterns.patternCount()}


def op_pattern_new_empty(a):
    # flag 2 = FFNEP_DontPromptName (no modal); it jumps to the empty pattern,
    # so read the resulting index from patternNumber().
    patterns.findFirstNextEmptyPat(2)
    return {"pattern": patterns.patternNumber()}


def op_pattern_length(a):
    n = int(a["num"])
    return {"num": n, "length": patterns.getPatternLength(n)}


def op_marker_add(a):
    import arrangement as _arr
    name = str(a["name"])
    t = _arr.currentTime(0)
    _arr.addAutoTimeMarker(t, name)
    return {"name": name, "time": t}


def _scan_markers():
    import arrangement as _arr
    out = []
    empties = 0
    i = 0
    while empties < 4 and i < 256:
        nm = _arr.getMarkerName(i)
        if nm:
            out.append({"index": i, "name": nm})
            empties = 0
        else:
            empties += 1
        i += 1
    return out


def op_markers_list(a):
    return {"markers": _scan_markers()}


def op_get_time(a):
    import arrangement as _arr
    active = bool(_arr.selectionIsActive()) if hasattr(_arr, "selectionIsActive") else False
    return {"time": _arr.currentTime(0),
            "selection_active": active,
            "sel_start": _arr.selectionStart(),
            "sel_end": _arr.selectionEnd()}


def op_select_region(a):
    import arrangement as _arr
    s = int(a["start"]); e = int(a["end"])
    _arr.selectionSet(s, e)
    return {"sel_start": _arr.selectionStart(), "sel_end": _arr.selectionEnd()}


def op_select_clear(a):
    import arrangement as _arr
    _arr.selectionClear()
    return {"cleared": True}


def op_channel_set_volume(a):
    ch = int(a["channel"]); v = float(a["volume"])
    channels.setChannelVolume(ch, v)
    return {"channel": ch, "volume": channels.getChannelVolume(ch)}


def op_channel_set_pan(a):
    ch = int(a["channel"]); p = float(a["pan"])
    channels.setChannelPan(ch, p)
    return {"channel": ch, "pan": channels.getChannelPan(ch)}


def op_channel_mute(a):
    ch = int(a["channel"])
    channels.muteChannel(ch)
    return {"channel": ch, "muted": bool(channels.isChannelMuted(ch))}


def op_route_channel(a):
    ch = int(a["channel"]); track = int(a["track"])
    n = mixer.trackCount()
    if track < 0 or track >= n:
        return {"error": "track %d out of range 0..%d" % (track, n - 1)}
    mixer.linkChannelToTrack(ch, track)
    return {"channel": ch, "mixer_track": channels.getTargetFxTrack(ch)}


def op_track_send(a):
    f = int(a["from_track"]); t = int(a["to_track"]); lvl = float(a.get("level", 1.0))
    mixer.setRouteTo(f, t, 1)
    if hasattr(mixer, "afterRoutingChanged"):
        mixer.afterRoutingChanged()
    try:
        mixer.setRouteToLevel(f, t, lvl)
    except Exception:
        pass
    return {"from": f, "to": t, "active": mixer.getRouteSendActive(f, t)}


def op_plugin_mix_level(a):
    t = int(a["track"]); slot = int(a["slot"]); lvl = float(a["level"])
    mixer.setPluginMixLevel(t, slot, lvl)
    return {"track": t, "slot": slot, "level": lvl}


def op_plugin_mute(a):
    t = int(a["track"]); slot = int(a["slot"]); val = int(a.get("value", 1))
    # confirmed signature: setPluginMuteState(track, slot, value)
    mixer.setPluginMuteState(t, slot, val)
    return {"track": t, "slot": slot, "muted": bool(val)}



def _dispatch(cmd):
    cid = cmd.get("id")
    op = cmd.get("op")
    args = cmd.get("args") or {}
    fn = OPS.get(op)
    if fn is None:
        return {"id": cid, "ok": False, "error": "unknown op: %s" % op}
    try:
        return {"id": cid, "ok": True, "result": fn(args)}
    except Exception as e:
        return {"id": cid, "ok": False, "error": "%s: %s" % (type(e).__name__, e)}


def _maybe_execute():
    global _last_id
    cmd = _read_command()
    if not cmd:
        return
    cid = cmd.get("id")
    # Execute on ANY id different from the last one (not strictly greater), so a
    # server restart that reseeds the id lower is still honored. Multi-trigger dedup
    # still holds: the same id firing ~4x/note runs once.
    if cid is None or cid == _last_id:
        return
    _last_id = cid
    _write_result(_dispatch(cmd))


def OnInit():
    print("FLClaudeMCP ready (FL %s)" % general.getVersion())


def OnMidiMsg(event):
    event.handled = True
    _maybe_execute()


def OnMidiIn(event):
    # some inputs arrive here; treat as trigger too (idempotent via id)
    _maybe_execute()
